"""Integration tests for the ``shutdown`` hooks of a real, running app.

Each test stands up its own ``RekuestNext`` (fresh ``AppRegistry`` via
:func:`build_fresh_rekuest`) against the shared deployment, boots it with a
``startup`` hook that produces a state, and asserts that the ``shutdown`` hook
runs on teardown — with the live state injected — on both the clean-exit and the
cancelled-loop path, and exactly once either way.
"""

import asyncio
from typing import List

import pytest
from dokker import Deployment

from .conftest import CONNECT_TIMEOUT, build_fresh_rekuest


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_shutdown_hook_runs_on_clean_exit(deployment: Deployment) -> None:
    """Leaving the app context manager runs the shutdown hook with the live state."""

    app = build_fresh_rekuest(deployment, token="standalone_token")
    registry = app.agent.app_registry
    torn_down: List[int] = []

    @registry.state
    class Counter:
        """The state a startup hook sets up and a shutdown hook releases."""

        count: int = 0

    def boot() -> Counter:
        """Set up the state the app runs with."""
        return Counter(count=42)

    async def teardown(counter: Counter) -> None:
        """Release whatever the app acquired."""
        torn_down.append(counter.count)

    app.register_startup(boot)
    app.register_shutdown(teardown)

    async with app as app:
        await app.aconnect(timeout=CONNECT_TIMEOUT)
        task = asyncio.create_task(app.aloop())

        assert torn_down == [], "The hook must not run while the agent is running"

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert torn_down == [42], (
        f"The shutdown hook should have run once with the live state, got {torn_down}"
    )


PERSISTED_PATCHES = """
query Sessions {
  sessions {
    id
    agent { id }
    patches { op path value interface }
  }
}
"""


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_state_mutated_in_a_shutdown_hook_reaches_the_backend(
    deployment: Deployment,
) -> None:
    """A state a shutdown hook mutates is published and persisted by the backend.

    The whole teardown-time publish path has to hold for this: the hooks run
    before the patch-queue flush, the socket outlives the cancelled agent loop
    (it is owned by the transport's connection task), and ``adisconnect`` flushes
    what is still queued before closing. This goes through the ordinary shutdown —
    cancel the loop — so it pins that path, not a special one.
    """

    app = build_fresh_rekuest(deployment, token="standalone_token")
    registry = app.agent.app_registry

    @registry.state
    class Counter:
        """The state the shutdown hook writes its last value into."""

        count: int = 0

    def boot() -> Counter:
        """Set up the state the app runs with."""
        return Counter(count=0)

    async def teardown(counter: Counter) -> None:
        """Record a final value on the way out."""
        counter.count = 7

    app.register_startup(boot)
    app.register_shutdown(teardown)

    async with app as app:
        await app.aconnect(timeout=CONNECT_TIMEOUT)
        task = asyncio.create_task(app.aloop())

        await asyncio.sleep(0.1)  # let the loop start and the socket come up
        agent_id = app.agent._agent.id

        # The ordinary shutdown: cancelling the loop tears the agent down, which
        # runs the hook, publishes its mutation, and flushes it on disconnect.
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert app.agent.global_revision > 0, (
            "The mutation in the hook should have produced a patch"
        )
        assert app.agent.transport._send_queue.qsize() == 0, (
            "The patch should have been flushed to the socket, not left queued"
        )

        await asyncio.sleep(0.5)  # give the backend a moment to persist
        result = await app.rath.aquery(PERSISTED_PATCHES, {})

    patches = [
        (patch["interface"], patch["op"], patch["path"], patch["value"])
        for session in result.data["sessions"]
        if session["agent"]["id"] == agent_id
        for patch in session["patches"]
    ]
    assert (Counter.__rekuest_state__, "replace", "/count", 7) in patches, (
        "The backend should have persisted the patch the shutdown hook wrote, "
        f"got {patches}"
    )


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_shutdown_hook_runs_once_when_the_loop_is_cancelled(
    deployment: Deployment,
) -> None:
    """Cancelling the agent loop tears it down — the hook still runs, and only once.

    The loop's cancellation path and the context manager's exit both tear the
    agent down, so this also pins the once-per-start guard.
    """

    app = build_fresh_rekuest(deployment, token="standalone_token")
    registry = app.agent.app_registry
    calls: List[str] = []

    @registry.state
    class Flag:
        """A trivial state, so the startup hook has something to publish."""

        up: bool = True

    def boot() -> Flag:
        """Set up the state the app runs with."""
        return Flag(up=True)

    async def exploding() -> None:
        """A hook that fails must not stop the others (it runs first, LIFO)."""
        calls.append("exploding")
        raise RuntimeError("teardown went wrong")

    async def teardown() -> None:
        """Release whatever the app acquired."""
        calls.append("teardown")

    app.register_startup(boot)
    app.register_shutdown(teardown)
    app.register_shutdown(exploding)

    async with app as app:
        await app.aconnect(timeout=CONNECT_TIMEOUT)
        task = asyncio.create_task(app.aloop())
        await asyncio.sleep(0.1)

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # The cancelled loop tears the agent down, so the hooks have run already.
        assert calls == ["exploding", "teardown"], (
            f"Hooks should run in reverse order despite the failure, got {calls}"
        )

    assert calls == ["exploding", "teardown"], (
        f"Teardown on context exit must not run the hooks a second time, got {calls}"
    )
