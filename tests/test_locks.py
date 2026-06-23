"""No-Docker checks for the consolidated lock layer.

These cover the consolidation of the lock logic into
``rekuest_next.agents.lock``: the agent builds one ``TaskLock`` per declared
lock key, ``LockGroup`` acquires overlapping key sets in sorted order (so
opposite declaration orders cannot deadlock), and the actor ``concurrency``
policy controls whether assignments to one actor run serially or in parallel.
"""

import asyncio

import pytest

from rekuest_next.agents.lock import LockGroup, TaskLock
from rekuest_next.api.schema import LockDefinitionInput, LockImplementationInput
from rekuest_next.rekuest import RekuestNext


def test_collect_from_extensions_builds_task_locks(mock_rekuest: RekuestNext) -> None:
    def snap(x: int) -> int:
        """Take a picture."""
        return x

    mock_rekuest.register(snap, locks=["camera"])

    agent = mock_rekuest.agent
    agent.collect_from_extensions()

    assert "camera" in agent.locks
    assert agent.get_locks_for_keys(["camera"]) == [agent.locks["camera"]]
    assert agent.get_locks_for_keys(["missing"]) == []


@pytest.mark.asyncio
async def test_overlapping_lock_groups_do_not_deadlock(
    mock_rekuest: RekuestNext,
) -> None:
    """Opposite declaration orders must still acquire in one global order."""

    def use_ab(x: int) -> int:
        """Use a then b."""
        return x

    def use_ba(x: int) -> int:
        """Use b then a."""
        return x

    mock_rekuest.register(use_ab, locks=["a", "b"])
    mock_rekuest.register(use_ba, locks=["b", "a"])

    agent = mock_rekuest.agent
    agent.collect_from_extensions()

    async def hammer(keys: tuple[str, ...], task: str) -> None:
        for _ in range(25):
            group = LockGroup(agent.get_locks_for_keys(keys), task)
            async with group:
                await asyncio.sleep(0)

    await asyncio.wait_for(
        asyncio.gather(hammer(("a", "b"), "assign-1"), hammer(("b", "a"), "assign-2")),
        timeout=5,
    )

    assert not agent.locks["a"].lock.locked()
    assert not agent.locks["b"].lock.locked()
    assert agent.locks["a"].locking_task is None


@pytest.mark.asyncio
async def test_failed_lock_notification_releases_the_local_lock() -> None:
    """Deadlock invariant 4: a failing ``alock`` must not leave the key held."""

    class FailingAgent:
        async def alock(self, key: str, task: str) -> None:
            raise RuntimeError("transport down")

        async def aunlock(self, key: str) -> None:
            return None

    task_lock = TaskLock(
        FailingAgent(),  # type: ignore[arg-type]
        LockImplementationInput(
            key="camera",
            definition=LockDefinitionInput(key="camera", description="The camera"),
        ),
    )

    with pytest.raises(RuntimeError, match="transport down"):
        await task_lock.acquire("assign-1")

    assert not task_lock.lock.locked()
    assert task_lock.locking_task is None


def _spawn_actor(mock_rekuest: RekuestNext, interface: str):
    builder = mock_rekuest.agent.app_registry.get_builder_for_interface(interface)
    return builder(agent=mock_rekuest.agent)


async def _enter_twice(actor, events: list[str]) -> None:
    async def run(task: str) -> None:
        async with actor.sync_context(task, "iface"):
            events.append(f"in-{task}")
            await asyncio.sleep(0.02)
            events.append(f"out-{task}")

    await asyncio.wait_for(asyncio.gather(run("1"), run("2")), timeout=5)


@pytest.mark.asyncio
async def test_parallel_actor_interleaves_assignments(
    mock_rekuest: RekuestNext,
) -> None:
    async def free(x: int) -> int:
        """No shared resources."""
        return x

    mock_rekuest.register(free, concurrency="parallel")
    mock_rekuest.agent.collect_from_extensions()

    events: list[str] = []
    await _enter_twice(_spawn_actor(mock_rekuest, "free"), events)

    # Both assignments are inside the context before either leaves.
    assert events[:2] == ["in-1", "in-2"]


@pytest.mark.asyncio
async def test_actor_serializes_assignments_by_default(
    mock_rekuest: RekuestNext,
) -> None:
    async def one_at_a_time(x: int) -> int:
        """Must not run concurrently with itself."""
        return x

    mock_rekuest.register(one_at_a_time)
    mock_rekuest.agent.collect_from_extensions()

    events: list[str] = []
    await _enter_twice(_spawn_actor(mock_rekuest, "one_at_a_time"), events)

    assert events == ["in-1", "out-1", "in-2", "out-2"]


@pytest.mark.asyncio
async def test_shared_lock_key_serializes_across_actors(
    mock_rekuest: RekuestNext,
) -> None:
    async def left(x: int) -> int:
        """Uses the camera."""
        return x

    async def right(x: int) -> int:
        """Also uses the camera."""
        return x

    mock_rekuest.register(left, locks=["camera"])
    mock_rekuest.register(right, locks=["camera"])
    mock_rekuest.agent.collect_from_extensions()

    left_actor = _spawn_actor(mock_rekuest, "left")
    right_actor = _spawn_actor(mock_rekuest, "right")

    events: list[str] = []

    async def run(actor, task: str) -> None:
        async with actor.sync_context(task, "iface"):
            events.append(f"in-{task}")
            await asyncio.sleep(0.02)
            events.append(f"out-{task}")

    await asyncio.wait_for(
        asyncio.gather(run(left_actor, "1"), run(right_actor, "2")), timeout=5
    )

    # Holding the shared key means the two actors never overlap.
    assert events in (
        ["in-1", "out-1", "in-2", "out-2"],
        ["in-2", "out-2", "in-1", "out-1"],
    )
