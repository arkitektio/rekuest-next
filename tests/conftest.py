"""Some configuration for pytest"""

from dataclasses import dataclass
from typing import AsyncGenerator, Awaitable, Callable, Generator
from uuid import uuid4
import pytest
from rekuest_next.app import AppRegistry
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.rekuest import RekuestNext, RekuestNextRath
from rath.links.testing.direct_succeeding_link import DirectSucceedingLink
from rekuest_next.agents.base import RekuestAgent
from rekuest_next.postmans.graphql import GraphQLPostman
from rekuest_next.agents.transport.websocket import WebsocketAgentTransport
import os
from dokker import local, Deployment, testing
from dokker.log_watcher import LogWatcher
from rath.links.auth import ComposedAuthLink
from rath.links.aiohttp import AIOHttpLink
from rath.links.graphql_ws import GraphQLWSLink
from rath.links.split import SplitLink
from graphql import OperationType
import pytest_asyncio
from rath.links.compose import compose


# Maximum time (seconds) to wait for an agent to connect and be acknowledged by
# the server before a test fails. Used with ``app.aconnect(timeout=...)``.
CONNECT_TIMEOUT = 5


def _dump_asyncio_tasks(signum: object, frame: object) -> None:
    """SIGALRM handler: dump every pending asyncio task's stack to stderr.

    Used to locate which coroutine is stuck when a test stalls. Enabled via the
    ``STALL_DEBUG`` env var (seconds).
    """
    import asyncio
    import sys

    try:
        loop = asyncio.get_event_loop()
        tasks = asyncio.all_tasks(loop)
    except Exception as exc:  # pragma: no cover - debug helper
        sys.stderr.write(f"\n##### STALL DUMP failed: {exc} #####\n")
        sys.stderr.flush()
        return
    sys.stderr.write(f"\n##### STALL DUMP: {len(tasks)} pending tasks #####\n")
    for task in tasks:
        sys.stderr.write(f"\n--- TASK {task!r}\n")
        task.print_stack(file=sys.stderr)
    sys.stderr.flush()


@pytest.fixture(autouse=True)
def _stall_watchdog():  # noqa: ANN202
    """Dump asyncio task stacks if a test runs longer than ``STALL_DEBUG`` seconds."""
    import os
    import signal

    seconds = os.environ.get("STALL_DEBUG")
    if not seconds:
        yield
        return
    signal.signal(signal.SIGALRM, _dump_asyncio_tasks)
    signal.setitimer(signal.ITIMER_REAL, float(seconds))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


class MockShelver:
    """A mock shelver that stores values in memory. This is used to test the
    shelver functionality without using a real shelver."""

    def __init__(self) -> None:
        """Initialize the mock shelver."""
        self.shelve: dict[str, object] = {}

    async def aput_on_shelve(self, identifier: str, value: object) -> str:
        """Put a value on the shelve and return the key. This is used to store
        values on the shelve."""
        key = str(id(value))
        self.shelve[key] = value
        return key

    async def aget_from_shelve(self, key: str) -> object:
        """Get a value from the shelve. This is used to get values from the
        shelve."""
        return self.shelve[key]


@pytest.fixture()
def simple_registry() -> StructureRegistry:
    """Fixture for a simple registry"""
    registry = StructureRegistry()

    return registry


@pytest.fixture()
def mock_shelver() -> MockShelver:
    """Fixture for a mock shelver"""
    return MockShelver()


@pytest.fixture()
def mock_rekuest() -> RekuestNext:
    """Fixture for a mock rekuest"""
    # This fixture can be used to mock the rekuest functionality if needed

    async def token_loader() -> str:
        """Mock token loader function."""
        return "mock_token"

    rath = RekuestNextRath(link=DirectSucceedingLink())

    agent = RekuestAgent(
        transport=WebsocketAgentTransport(
            endpoint_url="ws://localhost:8000/graphql",
            token_loader=token_loader,
        ),
        rath=rath,
        name="Test",
    )

    rath = RekuestNextRath(link=DirectSucceedingLink())

    x = RekuestNext(
        rath=rath,
        agent=agent,
        postman=GraphQLPostman(
            rath=rath,
        ),
    )

    return x


project_path = os.path.join(os.path.dirname(__file__), "integration")
docker_compose_file = os.path.join(project_path, "docker-compose.yml")
private_key = os.path.join(project_path, "private_key.pem")


async def token_loader() -> str:
    """Asynchronous function to load a token for authentication.

    This returns the "test" token which is configured as a static token to map to
    the user "test" in the test environment. In a real application, this function
    will return an oauth2 token or similar authentication token.

    To change this mapping you can alter the static_token configuration in the
    mikro configuration file (inside the integration folder).

    """
    return "test"


def make_token_loader(token: str = "test") -> Callable[[], Awaitable[str]]:
    """Build a token loader that always returns ``token``.

    The integration deployment is configured (see
    ``tests/integration/configs/rekuest.yaml``) with several static tokens, each
    mapping to a *different* ``client_app``. Authenticating an app with a given
    token therefore makes the server treat it as that distinct application. This
    is what lets several :func:`build_fresh_rekuest` apps run side by side as
    genuinely separate apps (e.g. a workflow app calling a provider app).

    Args:
        token: The static token to authenticate as. Must be one of the tokens
            configured in the deployment (``test``, ``atest_token``,
            ``btest_token``, ``workflow_token``, ``standalone_token``).

    Returns:
        An async, no-argument token loader suitable for the auth link and agent
        transport.
    """

    async def _loader() -> str:
        return token

    return _loader


@dataclass
class DeployedRekuest:
    """Dataclass to hold the deployed MikroNext application and its components."""

    deployment: Deployment
    rekuest_watcher: LogWatcher
    minio_watcher: LogWatcher
    rekuest: RekuestNext


def most_basic_function(hello: str) -> str:
    """Karl

    Karl takes a a representation and does magic stuff

    Args:
        hallo (str): Nougat

    Returns:
        str: The Returned Representation
    """
    return hello + " world"


@pytest.fixture(scope="session")
def deployed_app() -> Generator[DeployedRekuest, None, None]:
    """Fixture to deploy the MikroNext application with Docker Compose.

    This fixture sets up the MikroNext application using Docker Compose,
    configures health checks, and provides a deployed instance of MikroNext
    for testing purposes. It also includes watchers for the Mikro and MinIO
    services to monitor their logs, when performing requests against the application.

    Yields:
        DeployedMikro: An instance containing the deployment, watchers, and MikroNext instance

    """
    setup = testing(docker_compose_file)
    setup.add_health_check(
        url=lambda spec: (
            f"http://localhost:{spec.find_service('rekuest').get_port_for_internal(80).published}/graphql"
        ),
        service="rekuest",
        timeout=5,
        max_retries=10,
    )

    watcher = setup.create_watcher("rekuest")
    minio_watcher = setup.create_watcher("minio")

    with setup:
        setup.down()

        setup.pull()

        mikro_http_url = f"http://localhost:{setup.spec.find_service('rekuest').get_port_for_internal(80).published}/graphql"
        mikro_ws_url = f"ws://localhost:{setup.spec.find_service('rekuest').get_port_for_internal(80).published}/graphql"

        rath = RekuestNextRath(
            link=compose(
                ComposedAuthLink(
                    token_loader=token_loader, token_refresher=token_loader
                ),
                SplitLink(
                    left=AIOHttpLink(endpoint_url=mikro_http_url),
                    right=GraphQLWSLink(ws_endpoint_url=mikro_ws_url),
                    split=lambda o: o.node.operation != OperationType.SUBSCRIPTION,
                ),
            ),
        )

        agent = RekuestAgent(
            transport=WebsocketAgentTransport(
                endpoint_url=f"ws://localhost:{setup.spec.find_service('rekuest').get_port_for_internal(80).published}/agi",
                token_loader=token_loader,
            ),
            rath=rath,
            name="Test",
        )

        rekuest = RekuestNext(
            rath=rath,
            agent=agent,
            postman=GraphQLPostman(
                rath=rath,
            ),
        )
        setup.up()

        rekuest.register(most_basic_function)

        setup.check_health()

        with rekuest as rekuest:
            deployed = DeployedRekuest(
                deployment=setup,
                rekuest_watcher=watcher,
                minio_watcher=minio_watcher,
                rekuest=rekuest,
            )

            yield deployed


def build_fresh_rekuest(setup: Deployment, token: str = "test") -> RekuestNext:
    """Build a brand-new ``RekuestNext`` against an already-running deployment.

    Every call gets its own empty :class:`AppRegistry`, so registrations made by
    one test are completely invisible to the next. This is the per-test
    entrypoint for the integration tests: build the app, register functions on
    it, then run it against the shared docker stack.

    Args:
        setup: The running dokker deployment (from the ``deployment`` fixture).
        token: Static token to authenticate as. The deployment maps each
            configured token to a distinct ``client_app`` (see
            ``tests/integration/configs/rekuest.yaml``), so passing different
            tokens to different ``build_fresh_rekuest`` calls makes the server
            treat them as genuinely separate apps. The server binds the agent to
            its instance based on this authentication. Defaults to ``"test"``.

    Returns:
        A fresh, not-yet-entered ``RekuestNext`` client.
    """
    loader = make_token_loader(token)
    port = setup.spec.find_service("rekuest").get_port_for_internal(80).published
    http_url = f"http://localhost:{port}/graphql"
    ws_url = f"ws://localhost:{port}/graphql"
    agi_url = f"ws://localhost:{port}/agi"

    rath = RekuestNextRath(
        link=compose(
            ComposedAuthLink(token_loader=loader, token_refresher=loader),
            SplitLink(
                left=AIOHttpLink(endpoint_url=http_url),
                right=GraphQLWSLink(ws_endpoint_url=ws_url),
                split=lambda o: o.node.operation != OperationType.SUBSCRIPTION,
            ),
        ),
    )

    agent = RekuestAgent(
        transport=WebsocketAgentTransport(
            endpoint_url=agi_url,
            token_loader=loader,
        ),
        rath=rath,
        name=f"Test-{token}-{uuid4().hex[:8]}",
        app_registry=AppRegistry(),
    )

    return RekuestNext(
        rath=rath,
        agent=agent,
        postman=GraphQLPostman(rath=rath),
    )


@pytest_asyncio.fixture(scope="session")
async def deployment() -> AsyncGenerator[Deployment, None]:
    """Bring the rekuest stack up once per session and yield the dokker setup.

    Tests build their own fresh ``RekuestNext`` (fresh ``AppRegistry``, unique
    instance id) against this running stack via :func:`build_fresh_rekuest`, so
    no registry state ever leaks between tests.
    """
    setup = local(docker_compose_file)
    setup.pull_on_enter = False
    setup.down_on_exit = True
    setup.up_on_enter = False
    setup.add_health_check(
        url=lambda spec: (
            f"http://localhost:{spec.find_service('rekuest').get_port_for_internal(80).published}/graphql"
        ),
        service="rekuest",
        timeout=5,
        max_retries=10,
    )

    async with setup:
        await setup.adown()
        await setup.apull()
        await setup.aup()
        await setup.acheck_health()
        yield setup


@pytest_asyncio.fixture(scope="session")
async def async_deployed_app(
    deployment: Deployment,
) -> AsyncGenerator[DeployedRekuest, None]:
    """A deployed app with ``most_basic_function`` registered on a fresh registry.

    Built on top of the shared ``deployment`` fixture via
    :func:`build_fresh_rekuest`, so it too gets its own ``AppRegistry``.
    """
    watcher = deployment.create_watcher("rekuest")
    minio_watcher = deployment.create_watcher("minio")

    rekuest = build_fresh_rekuest(deployment)
    rekuest.register(most_basic_function)

    async with rekuest as rekuest:
        deployed = DeployedRekuest(
            deployment=deployment,
            rekuest_watcher=watcher,
            minio_watcher=minio_watcher,
            rekuest=rekuest,
        )

        yield deployed
