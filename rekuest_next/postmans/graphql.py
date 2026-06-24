"""A GraphQL postman"""

from types import TracebackType
from typing import AsyncGenerator, Dict, List
from rekuest_next.api.schema import (
    TaskChange,
    TaskEventChange,
    TaskEventKind,
    aassign,
    awatch_my_tasks,
    acancel,
    ainterrupt,
    AssignInput,
)
import asyncio
from pydantic import Field, PrivateAttr
import logging
from .errors import PostmanException
from rekuest_next.rath import RekuestNextRath
from koil.composition import KoiledModel
from .vars import current_postman

logger = logging.getLogger(__name__)


class GraphQLPostman(KoiledModel):
    """A GraphQL Postman

    This postman is used to send messages to the GraphQL server via a graphql
    transport.

    This graphql postman

    """

    rath: RekuestNextRath
    connected: bool = Field(default=False)
    tasks: Dict[str, TaskChange] = Field(default_factory=dict)
    cancel_timeout: float = Field(
        default=5.0,
        description="Maximum seconds to wait for the server to confirm cancellation of a task when an assign stream is cancelled. Bounds cancellation so cancelling a call can never hang.",
    )

    _ass_update_queues: Dict[str, asyncio.Queue[TaskEventChange]] = PrivateAttr(
        default_factory=lambda: {}
    )
    # The change feed (TaskEventChange) only carries the task id, not the
    # client-generated reference the queues are keyed by, so we bind them here.
    # An event can arrive before that binding is known (websocket faster than the
    # assign http response, or an event before its create), so unbound events are
    # buffered and flushed in `_bind`.
    _task_to_reference: Dict[str, str] = PrivateAttr(default_factory=lambda: {})
    _reference_to_task: Dict[str, str] = PrivateAttr(default_factory=lambda: {})
    _orphan_events_by_task: Dict[str, List[TaskEventChange]] = PrivateAttr(
        default_factory=lambda: {}
    )
    _watch_tasks_task: asyncio.Task[None] | None = None

    _watching: bool = PrivateAttr(default=False)
    _lock: asyncio.Lock | None = None
    _received_something: bool = False

    def _bind(self, task_id: str, reference: str) -> None:
        """Bind a durable task id to its client-generated reference.

        Records both directions and flushes any events that arrived for this task
        before the binding was known into the reference's queue.
        """
        self._task_to_reference[task_id] = reference
        self._reference_to_task[reference] = task_id
        orphans = self._orphan_events_by_task.pop(task_id, [])
        queue = self._ass_update_queues.get(reference)
        if queue is not None:
            for event in orphans:
                queue.put_nowait(event)

    async def aassign(
        self,
        assign: AssignInput,
        escalate_to_interrupt: bool = False,
        cancel_timeout: float | None = None,
    ) -> AsyncGenerator[TaskEventChange, None]:
        """Assign a"""
        if not self._received_something:
            await asyncio.sleep(0.5)  # Add an initial sleep

        if not assign.reference:
            raise Exception("Reference must be set. Before assigning")

        if not self._lock:
            raise ValueError("Postman was never connected")

        async with self._lock:
            if not self._watching:
                await self.start_watching()

        self._ass_update_queues[assign.reference] = asyncio.Queue()
        queue = self._ass_update_queues[assign.reference]

        try:
            task = await aassign(**assign.model_dump(), rath=self.rath)
        except Exception as e:
            raise PostmanException(f"Cannot Assign: {e}") from e

        # Bind task id -> reference so the change feed (which only knows the task
        # id) can route events to this queue. Also flushes any events that raced
        # ahead of this http response.
        self._bind(task.id, assign.reference)

        try:
            while True:
                signal = await queue.get()
                yield signal
                queue.task_done()

        except asyncio.CancelledError as e:
            # Tell the server to cancel and await the CANCELLED confirmation (and,
            # if requested, escalate to an interrupt) before re-raising. The whole
            # exchange is bounded by `cancel_timeout`, so cancelling can never hang.
            try:
                await self._confirm_cancellation(
                    task.id,
                    queue,
                    escalate_to_interrupt,
                    cancel_timeout if cancel_timeout is not None else self.cancel_timeout,
                )
            finally:
                self._cleanup_reference(assign.reference)
            raise e

    def _cleanup_reference(self, reference: str) -> None:
        """Drop all per-call state for a finished/cancelled assignation."""
        tid = self._reference_to_task.pop(reference, None)
        if tid is not None:
            self._task_to_reference.pop(tid, None)
            self._orphan_events_by_task.pop(tid, None)
        self._ass_update_queues.pop(reference, None)

    async def _confirm_cancellation(
        self,
        task_id: str,
        queue: "asyncio.Queue[TaskEventChange]",
        escalate_to_interrupt: bool,
        timeout: float,
    ) -> None:
        """Cancel a task and await its CANCELLED (or escalated INTERRUPTED) event.

        Sends the cancel, then waits up to ``timeout`` for the backend to confirm
        via a CANCELLED task event. If that does not arrive and
        ``escalate_to_interrupt`` is set, sends a forceful interrupt and waits for
        the INTERRUPTED confirmation. Every wait is bounded, so this never hangs.
        """
        await self._send_cancel(task_id, timeout)
        if await self._await_kind(queue, {TaskEventKind.CANCELLED}, timeout):
            return

        if not escalate_to_interrupt:
            logger.warning(
                "Timed out awaiting CANCELLED confirmation for task %s", task_id
            )
            return

        await self._send_interrupt(task_id, timeout)
        if not await self._await_kind(
            queue, {TaskEventKind.INTERRUPTED, TaskEventKind.CANCELLED}, timeout
        ):
            logger.warning(
                "Timed out awaiting INTERRUPTED confirmation for task %s", task_id
            )

    async def _send_cancel(self, task_id: str, timeout: float) -> None:
        """Request a graceful cancel of the task (best-effort, bounded)."""
        try:
            await asyncio.wait_for(
                acancel(task=task_id, rath=self.rath), timeout=timeout
            )
        except Exception:
            logger.warning(
                "Failed to request cancel for task %s", task_id, exc_info=True
            )

    async def _send_interrupt(self, task_id: str, timeout: float) -> None:
        """Request a forceful interrupt of the task (best-effort, bounded)."""
        try:
            await asyncio.wait_for(
                ainterrupt(task=task_id, rath=self.rath), timeout=timeout
            )
        except Exception:
            logger.warning(
                "Failed to request interrupt for task %s", task_id, exc_info=True
            )

    async def _await_kind(
        self,
        queue: "asyncio.Queue[TaskEventChange]",
        kinds: "set[TaskEventKind]",
        timeout: float,
    ) -> bool:
        """Drain ``queue`` until an event of one of ``kinds`` arrives.

        Bounded by ``timeout`` overall. Returns ``True`` if a matching event was
        seen, ``False`` on timeout.
        """
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                return False
            try:
                event = await asyncio.wait_for(queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                return False
            if event.kind in kinds:
                return True

    async def watch_tasks(self) -> None:
        """Watch this client's tasks and route their events to per-call queues.

        The change feed yields slim, non-traversable snapshots: ``create`` is a
        ``TaskChange`` (carrying both the task id and the reference) and ``event``
        is a ``TaskEventChange`` (carrying only the task id). We bind on ``create``
        and route on ``event``, buffering events whose task id is not yet bound.
        """
        try:
            async for change in awatch_my_tasks(rath=self.rath):
                self._received_something = True
                if change.create and change.create.reference:
                    self._bind(change.create.id, change.create.reference)
                if change.event:
                    reference = self._task_to_reference.get(change.event.task)
                    queue = (
                        self._ass_update_queues.get(reference)
                        if reference is not None
                        else None
                    )
                    if queue is not None:
                        await queue.put(change.event)
                    else:
                        # Task id not bound to a live reference yet: buffer the
                        # event and flush it once `_bind` learns the reference.
                        self._orphan_events_by_task.setdefault(
                            change.event.task, []
                        ).append(change.event)

        except Exception as e:
            logger.error("Watching Tasks failed", exc_info=True)
            raise e

    async def start_watching(self) -> None:
        """Start watching for updates"""
        logger.info("Starting watching")
        self._watch_tasks_task = asyncio.create_task(self.watch_tasks())
        self._watch_tasks_task.add_done_callback(self.log_task_fail)
        self._watching = True

    def log_task_fail(self, task: asyncio.Task[None]) -> None:
        """a hook to"""
        return

    async def stop_watching(self) -> None:
        """Causes the postman to stop watching"""
        if self._watch_tasks_task:
            self._watch_tasks_task.cancel()

            try:
                await asyncio.gather(
                    self._watch_tasks_task,
                    return_exceptions=True,
                )
            except asyncio.CancelledError:
                pass

        self._watching = False

    async def __aenter__(self) -> "GraphQLPostman":
        """Enter the postman"""
        self._lock = asyncio.Lock()
        current_postman.set(self)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context manager"""
        if self._watching:
            await self.stop_watching()
        current_postman.set(None)
        return await super().__aexit__(exc_type, exc_val, exc_tb)
