"""Some configuration for pytest"""

from dataclasses import dataclass
from typing import AsyncGenerator, Generator
import pytest
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.rekuest import RekuestNext, RekuestNextRath
from rekuest_next.rath import RekuestNextLinkComposition, RekuestNextRath
from rath.links.testing.direct_succeeding_link import DirectSucceedingLink
from rekuest_next.agents.base import RekuestAgent
from rekuest_next.postmans.graphql import GraphQLPostman
from rekuest_next.agents.transport.websocket import WebsocketAgentTransport
import os
from dokker import local, Deployment
from dokker.log_watcher import LogWatcher
from rath.links.auth import ComposedAuthLink
from rath.links.aiohttp import AIOHttpLink
from rath.links.graphql_ws import GraphQLWSLink
from rath.links.split import SplitLink
from graphql import OperationType
import pytest_asyncio


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

    instance_id = "default"

    async def token_loader() -> str:
        """Mock token loader function."""
        return "mock_token"

    rath = RekuestNextRath(link=DirectSucceedingLink())

    agent = RekuestAgent(
        transport=WebsocketAgentTransport(
            endpoint_url="ws://localhost:8000/graphql",
            token_loader=token_loader,
        ),
        instance_id=instance_id,
        rath=rath,
        name="Test",
    )

    rath = RekuestNextRath(link=DirectSucceedingLink())

    x = RekuestNext(
        rath=rath,
        agent=agent,
        postman=GraphQLPostman(
            rath=rath,
            instance_id=instance_id,
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


@dataclass
class DeployedRekuest:
    """Dataclass to hold the deployed MikroNext application and its components."""

    deployment: Deployment
    rekuest_watcher: LogWatcher
    minio_watcher: LogWatcher
    rekuest: RekuestNext
    instance_id: str = "default"


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
    setup = local(docker_compose_file)
    setup.pull_on_enter = False
    setup.down_on_exit = True
    setup.up_on_enter = False
    setup.add_health_check(
        url=lambda spec: f"http://localhost:{spec.find_service('rekuest').get_port_for_internal(80).published}/graphql",
        service="mikro",
        timeout=5,
        max_retries=10,
    )

    watcher = setup.create_watcher("rekuest")
    minio_watcher = setup.create_watcher("minio")

    with setup:
        setup.down()

        setup.pull()

        instance_id = "default"

        mikro_http_url = f"http://localhost:{setup.spec.find_service('rekuest').get_port_for_internal(80).published}/graphql"
        mikro_ws_url = f"ws://localhost:{setup.spec.find_service('rekuest').get_port_for_internal(80).published}/graphql"

        rath = RekuestNextRath(
            link=RekuestNextLinkComposition(
                auth=ComposedAuthLink(token_loader=token_loader, token_refresher=token_loader),
                split=SplitLink(
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
            instance_id=instance_id,
            rath=rath,
            name="Test",
        )

        rekuest = RekuestNext(
            rath=rath,
            agent=agent,
            postman=GraphQLPostman(
                rath=rath,
                instance_id=instance_id,
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
                instance_id=instance_id,
            )

            yield deployed


@pytest_asyncio.fixture(scope="session")
@pytest.mark.asyncio(scope="session")
async def async_deployed_app() -> AsyncGenerator[DeployedRekuest, None]:
    """Fixture to deploy the MikroNext application with Docker Compose.

    This fixture sets up the MikroNext application using Docker Compose,
    configures health checks, and provides a deployed instance of MikroNext
    for testing purposes. It also includes watchers for the Mikro and MinIO
    services to monitor their logs, when performing requests against the application.

    Yields:
        DeployedMikro: An instance containing the deployment, watchers, and MikroNext instance

    """
    setup = local(docker_compose_file)
    setup.pull_on_enter = False
    setup.down_on_exit = True
    setup.up_on_enter = False
    setup.add_health_check(
        url=lambda spec: f"http://localhost:{spec.find_service('rekuest').get_port_for_internal(80).published}/graphql",
        service="mikro",
        timeout=5,
        max_retries=10,
    )

    watcher = setup.create_watcher("rekuest")
    minio_watcher = setup.create_watcher("minio")

    async with setup:
        await setup.adown()
        await setup.apull()

        instance_id = "default"

        mikro_http_url = f"http://localhost:{setup.spec.find_service('rekuest').get_port_for_internal(80).published}/graphql"
        mikro_ws_url = f"ws://localhost:{setup.spec.find_service('rekuest').get_port_for_internal(80).published}/graphql"

        rath = RekuestNextRath(
            link=RekuestNextLinkComposition(
                auth=ComposedAuthLink(token_loader=token_loader, token_refresher=token_loader),
                split=SplitLink(
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
            instance_id=instance_id,
            rath=rath,
            name="Test",
        )

        rekuest = RekuestNext(
            rath=rath,
            agent=agent,
            postman=GraphQLPostman(
                rath=rath,
                instance_id=instance_id,
            ),
        )
        await setup.aup()

        rekuest.register(most_basic_function)

        await setup.acheck_health()

        async with rekuest as rekuest:
            deployed = DeployedRekuest(
                deployment=setup,
                rekuest_watcher=watcher,
                minio_watcher=minio_watcher,
                rekuest=rekuest,
                instance_id=instance_id,
            )

            yield deployed
