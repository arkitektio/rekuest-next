"""Runtime locks shared between actors of one agent.

This is the single home of the lock logic: ``TaskLock`` is the per-key lock
(one per registered lock schema, owned by the agent) and ``LockGroup`` is the
set of ``TaskLock``s an assignment must hold while it runs, acquired through
:meth:`rekuest_next.actors.base.Actor.sync_context`.

Deadlock invariants
-------------------

1. **Global ordering** — ``LockGroup`` sorts its locks by ``lock_key`` before
   acquiring, so any two assignments acquiring overlapping key sets always take
   them in the same order. AB/BA cycles between actors are therefore
   impossible, no matter in which order the keys were declared.
2. **Ordering across mechanisms** — an actor with ``concurrency="serial"``
   acquires its private serial lock *before* the shared keys (see
   ``Actor.sync_context``). The serial lock is never contended outside its
   actor and a waiter on it holds nothing, so it cannot participate in a
   cycle; shared keys are only held while an assignment actually runs, never
   while it is queued behind its actor.
3. **Non-reentrancy** — ``asyncio.Lock`` is not reentrant. An assignment that
   holds key ``K`` and calls — directly or via a dependency — another
   implementation on the same agent that also requires ``K`` will deadlock.
   The same applies to a ``"serial"`` actor calling itself.
4. **Network calls while holding** — ``agent.alock``/``aunlock`` are awaited
   while the local ``asyncio.Lock`` is held so the server observes lock and
   unlock events in their true order. Every failure path must release the
   local lock; ``TaskLock.acquire`` and ``TaskLock.release`` guarantee this.
"""

import asyncio
import logging
from types import TracebackType
from rekuest_next.api.schema import LockImplementationInput
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from rekuest_next.actors.types import Agent

logger = logging.getLogger(__name__)


class TaskLock:
    """A named lock shared by all implementations that declare its key.

    Wraps a local ``asyncio.Lock`` and mirrors acquire/release to the agent
    (``agent.alock``/``aunlock``) so the server can display lock state.
    """

    def __init__(self, agent: "Agent", lock: "LockImplementationInput"):
        self.agent = agent
        self.lock = asyncio.Lock()
        self.lock_key = lock.definition.key
        self.locking_task: str | None = None
        self.definition = lock.definition

    async def acquire(self, task: str) -> None:
        """Acquire the lock for a task and notify the agent.

        If notifying the agent fails, the local lock is released again so the
        key cannot be left held forever (deadlock invariant 4).
        """
        await self.lock.acquire()
        try:
            self.locking_task = task
            await self.agent.alock(self.definition.key, task)
        except BaseException:
            self.locking_task = None
            self.lock.release()
            raise

    async def release(self) -> None:
        """Notify the agent and release the lock.

        The agent is notified while the local lock is still held so the server
        sees lock/unlock events in their true order; the local lock is released
        even if the notification fails (deadlock invariant 4).
        """
        self.locking_task = None
        try:
            await self.agent.aunlock(self.lock_key)
        finally:
            self.lock.release()


class LockGroup:
    """The set of task locks an assignment holds while it runs.

    Acquires the locks in sorted key order (deadlock invariant 1) and releases
    them in reverse. Use as an async context manager.
    """

    def __init__(
        self,
        locks: list[TaskLock],
        task_id: str,
    ) -> None:
        """Initialize the LockGroup.

        Args:
            locks: The TaskLock instances to acquire.
            task_id: The ID of the task acquiring them.
        """
        self.locks = locks
        self.task_id = task_id
        self._acquired_locks: list[TaskLock] = []

    async def acquire(self) -> Self:
        """Acquire all locks in sorted key order.

        Returns:
            LockGroup: This group, with all locks held.
        """
        for lock in sorted(self.locks, key=lambda x: x.lock_key):
            await lock.acquire(self.task_id)
            self._acquired_locks.append(lock)
        return self

    async def release(self) -> None:
        """Release all acquired locks in reverse order.

        Best-effort: a failing release does not leave the remaining keys held.
        """
        for lock in reversed(self._acquired_locks):
            try:
                await lock.release()
            except Exception:
                logger.exception("Failed to release lock %s", lock.lock_key)
        self._acquired_locks.clear()

    async def __aenter__(self) -> Self:
        """Acquire all locks (sorted) and return the group."""
        try:
            return await self.acquire()
        except BaseException:
            await self.release()
            raise

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Release all acquired locks."""
        await self.release()
