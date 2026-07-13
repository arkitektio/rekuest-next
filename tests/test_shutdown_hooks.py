"""No-Docker checks for the shutdown hooks the agent runs while tearing down.

These cover what ``BaseAgent.arun_shutdown_hooks`` guarantees: hooks are
collected from the app registry, run in the reverse of their registration order
with the live states and contexts injected by annotation, a failing hook does
not stop the remaining ones, and hooks only run for an agent that actually got
through its startup hooks — exactly once per start.
"""

from typing import Generator, List

import pytest

from rekuest_next import context, state
from rekuest_next.agents.hooks.shutdown import (
    ThreadedShutdownHook,
    WrappedShutdownHook,
)
from rekuest_next.rekuest import RekuestNext


@context
class Connection:
    """A context holding something a shutdown hook has to close."""

    def __init__(self) -> None:
        self.closed = False


@state
class Counter:
    """A state a shutdown hook may want to read one last time."""

    count: int = 3


@pytest.fixture(autouse=True)
def _isolated_hooks(mock_rekuest: RekuestNext) -> Generator[None, None, None]:
    """The agent defaults to the global app registry, which other test modules also
    decorate into. Start (and leave) each test with an empty hooks registry."""
    registry = mock_rekuest.agent.app_registry.hooks_registry
    registry.reset()
    yield
    registry.reset()


def test_register_shutdown_lands_in_the_registry(mock_rekuest: RekuestNext) -> None:
    def close_it() -> None:
        pass

    async def aclose_it() -> None:
        pass

    mock_rekuest.register_shutdown(close_it)
    mock_rekuest.register_shutdown(aclose_it)

    hooks = mock_rekuest.agent.app_registry.hooks_registry.shutdown_hooks
    assert isinstance(hooks["close_it"], ThreadedShutdownHook)
    assert isinstance(hooks["aclose_it"], WrappedShutdownHook)


def test_app_registry_shutdown_decorator(mock_rekuest: RekuestNext) -> None:
    """The registry-bound decorator registers on that registry, under a given name."""
    registry = mock_rekuest.agent.app_registry

    @registry.shutdown
    async def close_it() -> None:
        pass

    @registry.shutdown(name="renamed")
    async def close_that_too() -> None:
        pass

    hooks = registry.hooks_registry.shutdown_hooks
    assert isinstance(hooks["close_it"], WrappedShutdownHook)
    assert isinstance(hooks["renamed"], WrappedShutdownHook)


@pytest.mark.asyncio
async def test_shutdown_hooks_run_with_states_and_contexts(
    mock_rekuest: RekuestNext,
) -> None:
    """The live state and context objects are injected by annotation."""
    seen: List[object] = []

    async def close_connection(connection: Connection, counter: Counter) -> None:
        connection.closed = True
        seen.append(counter)

    mock_rekuest.register_shutdown(close_connection)

    agent = mock_rekuest.agent
    connection, counter = Connection(), Counter()
    agent.contexts[Connection.__rekuest_context__] = connection
    agent.states[Counter.__rekuest_state__] = counter

    agent.collect_from_extensions()
    agent._ran_startup_hooks = True
    await agent.arun_shutdown_hooks()

    assert connection.closed, "The hook should have received the live context"
    assert seen == [counter], "The hook should have received the live state"


@pytest.mark.asyncio
async def test_threaded_shutdown_hook_runs_with_states_and_contexts(
    mock_rekuest: RekuestNext,
) -> None:
    """A sync hook runs in a thread, and gets the same injection as an async one."""
    seen: List[object] = []

    def close_connection(connection: Connection, counter: Counter) -> None:
        connection.closed = True
        seen.append(counter)

    mock_rekuest.register_shutdown(close_connection)

    agent = mock_rekuest.agent
    connection, counter = Connection(), Counter()
    agent.contexts[Connection.__rekuest_context__] = connection
    agent.states[Counter.__rekuest_state__] = counter

    agent.collect_from_extensions()
    agent._ran_startup_hooks = True
    await agent.arun_shutdown_hooks()

    assert connection.closed, "The threaded hook should have received the live context"
    assert seen == [counter], "The threaded hook should have received the live state"


@pytest.mark.asyncio
async def test_shutdown_hooks_run_in_reverse_registration_order(
    mock_rekuest: RekuestNext,
) -> None:
    """Teardown unwinds in the reverse of the order things were set up."""
    calls: List[str] = []

    async def first() -> None:
        calls.append("first")

    async def second() -> None:
        calls.append("second")

    mock_rekuest.register_shutdown(first)
    mock_rekuest.register_shutdown(second)

    agent = mock_rekuest.agent
    agent.collect_from_extensions()
    agent._ran_startup_hooks = True
    await agent.arun_shutdown_hooks()

    assert calls == ["second", "first"]


@pytest.mark.asyncio
async def test_failing_shutdown_hook_does_not_stop_the_others(
    mock_rekuest: RekuestNext,
) -> None:
    """A hook that raises is logged; teardown carries on."""
    calls: List[str] = []

    async def survivor() -> None:
        calls.append("survivor")

    async def exploding() -> None:
        raise RuntimeError("nope")

    mock_rekuest.register_shutdown(survivor)
    mock_rekuest.register_shutdown(exploding)  # runs first (reverse order)

    agent = mock_rekuest.agent
    agent.collect_from_extensions()
    agent._ran_startup_hooks = True

    await agent.arun_shutdown_hooks()

    assert calls == ["survivor"], "The failing hook must not abort the remaining ones"


@pytest.mark.asyncio
async def test_shutdown_hooks_only_run_for_a_started_agent_and_only_once(
    mock_rekuest: RekuestNext,
) -> None:
    calls: List[str] = []

    async def close_it() -> None:
        calls.append("closed")

    mock_rekuest.register_shutdown(close_it)

    agent = mock_rekuest.agent
    agent.collect_from_extensions()

    # Never started: teardown owes it nothing.
    await agent.arun_shutdown_hooks()
    assert calls == []

    agent._ran_startup_hooks = True
    await agent.arun_shutdown_hooks()
    await agent.arun_shutdown_hooks()
    assert calls == ["closed"], "Hooks must run exactly once per start"
