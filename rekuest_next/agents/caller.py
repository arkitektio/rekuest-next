"""The agent-as-caller postman.

When actor code calls another action or a dependency *from inside a running task*,
the call should travel over the agent's own WebSocket as an ``AssignRequest`` instead of
going out through the GraphQL postman. ``AgentPostman`` is the object that makes that work:
it satisfies the :class:`~rekuest_next.postmans.types.Postman` protocol (``aassign`` →
``AsyncGenerator`` of task events), so every existing call path in
:mod:`rekuest_next.remote` (``acall`` / ``aiterate`` / ``acall_dependency``) routes through
it unchanged once it is bound as ``current_postman`` while an actor body runs (see
:meth:`rekuest_next.actors.helper.AssignmentHelper.__enter__`).

The translation is:

- outbound: an ``AssignInput`` (the postman call shape) → an ``AssignRequest`` socket message;
  ``AssignInput.reference`` is reused as the idempotency key.
- inbound: the backend answers with an ``AssignResponse`` (carrying the durable task id) and
  then streams ``ExecutionEvent`` mirrors for that task. Each surfaced mirror is adapted into a
  :class:`CallerTaskEvent` that exposes exactly the ``.kind`` / ``.returns`` / ``.message``
  attributes ``rekuest_next.remote._astream_raw`` reads.

The agent's message loop (``BaseAgent.process``) forwards ``AssignResponse`` /
``ControlResponse`` / ``ExecutionEvent`` here via the ``handle_*`` methods.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from types import TracebackType
from typing import TYPE_CHECKING, AsyncGenerator, Dict, List, Optional

from rekuest_next import messages
from rekuest_next.api.schema import AssignInput, TaskEventKind
from rekuest_next.postmans.errors import AssignException

if TYPE_CHECKING:
    from rekuest_next.agents.base import BaseAgent

logger = logging.getLogger(__name__)


@dataclass
class CallerTaskEvent:
    """A minimal ``TaskEvent`` look-alike.

    ``rekuest_next.remote._astream_raw`` only ever reads ``.kind`` (compared against
    :class:`TaskEventKind`), ``.returns`` and ``.message`` — so this three-field adapter is
    enough to drive the existing call machinery without constructing a full (frozen,
    field-heavy) GraphQL ``TaskEvent``.
    """

    kind: TaskEventKind
    returns: Optional[Dict[str, object]] = None
    message: Optional[str] = None


#: Mirror message types that map onto a streamed ``CallerTaskEvent``. Every other mirror
#: (Bound/Queued/Started/Progress/Log/Delegate/Disconnected/…ing/…ed) is consumed for
#: bookkeeping only — ``_astream_raw`` would ignore it anyway.
_TERMINAL_TYPES = (
    messages.CompletedEvent,
    messages.FailedEvent,
    messages.CriticalEvent,
    messages.CancelledEvent,
    messages.InterruptedEvent,
)


def _adapt(event: "messages.ExecutionEvent") -> Optional[CallerTaskEvent]:
    """Translate a backend mirror into a ``CallerTaskEvent`` (or ``None`` to skip).

    Only the four kinds ``_astream_raw`` acts on are surfaced. ``Cancelled``/``Interrupted``
    are surfaced as a ``CRITICAL`` so an in-flight ``acall`` fails loudly rather than hanging
    or silently completing when the work it delegated was killed out from under it.
    """
    if isinstance(event, messages.YieldEvent):
        return CallerTaskEvent(kind=TaskEventKind.YIELD, returns=event.returns)
    if isinstance(event, messages.CompletedEvent):
        return CallerTaskEvent(kind=TaskEventKind.COMPLETED)
    if isinstance(event, messages.FailedEvent):
        return CallerTaskEvent(kind=TaskEventKind.FAILED, message=event.error)
    if isinstance(event, messages.CriticalEvent):
        return CallerTaskEvent(kind=TaskEventKind.CRITICAL, message=event.error)
    if isinstance(event, (messages.CancelledEvent, messages.InterruptedEvent)):
        return CallerTaskEvent(
            kind=TaskEventKind.CRITICAL,
            message="The delegated task was cancelled or interrupted before completion.",
        )
    return None


class AgentPostman:
    """A :class:`Postman` that originates work over the agent's socket.

    A single instance is shared by every actor on the agent; all per-call state is keyed by
    request id / task id, so concurrent calls never collide.
    """

    def __init__(self, agent: "BaseAgent", cancel_timeout: float = 5.0) -> None:
        self.agent = agent
        # Max seconds to await a CANCELLED/INTERRUPTED confirmation when an assign
        # stream is cancelled. Bounds cancellation so it can never hang.
        self.cancel_timeout = cancel_timeout
        # request id -> future resolved with the AssignResponse
        self._pending_responses: Dict[
            str, "asyncio.Future[messages.AssignResponse]"
        ] = {}
        # control request id -> future resolved with the ControlResponse
        self._pending_control: Dict[
            str, "asyncio.Future[messages.ControlResponse]"
        ] = {}
        # durable task id -> queue of ExecutionEvent mirrors
        self._task_queues: Dict[str, "asyncio.Queue[messages.ExecutionEvent]"] = {}
        # task id -> mirrors that arrived before the AssignResponse was processed
        self._orphan_by_task: Dict[str, List["messages.ExecutionEvent"]] = {}
        # idempotency reference -> durable task id
        self._reference_to_task: Dict[str, str] = {}
        # task id -> last seen seq (gap detection only)
        self._last_seq: Dict[str, int] = {}

    @property
    def connected(self) -> bool:
        """Whether the underlying agent transport is connected."""
        return getattr(self.agent.transport, "connected", False)

    # ------------------------------------------------------------------ outbound

    def _build_request(
        self, assign: AssignInput, reference: str
    ) -> messages.AssignRequest:
        """Translate an ``AssignInput`` into an ``AssignRequest`` socket message."""
        return messages.AssignRequest(
            reference=reference,
            args=dict(assign.args or {}),
            action=assign.action,
            action_hash=assign.action_hash,
            implementation=assign.implementation,
            agent=assign.agent,
            interface=assign.interface,
            parent=assign.parent,
            dependency=assign.dependency,
            method=assign.method,
            resolution=assign.resolution,
            hooks=[h.model_dump(by_alias=True) for h in (assign.hooks or [])],
            capture=assign.capture,
            ephemeral=assign.ephemeral,
            step=assign.step,
        )

    async def aassign(
        self,
        assign: AssignInput,
        escalate_to_interrupt: bool = False,
        cancel_timeout: Optional[float] = None,
    ) -> AsyncGenerator[CallerTaskEvent, None]:
        """Originate a task over the agent socket and stream its events.

        Sends an ``AssignRequest``, awaits the ``AssignResponse`` (to learn the durable task
        id), then yields a ``CallerTaskEvent`` for every surfaced mirror until a terminal one
        arrives. On cancellation a ``CancelRequest`` is sent and the ``CancelledEvent``
        confirmation is awaited (bounded by ``cancel_timeout``); if ``escalate_to_interrupt``
        is set and the cancel is not confirmed in time, an ``InterruptRequest`` follows.
        """
        reference = assign.reference or str(uuid.uuid4())
        request = self._build_request(assign, reference)
        loop = asyncio.get_event_loop()
        response_future: "asyncio.Future[messages.AssignResponse]" = (
            loop.create_future()
        )
        self._pending_responses[request.id] = response_future

        task: Optional[str] = None
        queue: Optional["asyncio.Queue[messages.ExecutionEvent]"] = None
        try:
            await self.agent.transport.asend(request)
            response = await response_future

            if response.error:
                raise AssignException(response.error)
            if not response.task:
                raise AssignException(
                    "The backend acked the assign without a task id and without an error."
                )

            task = response.task
            queue = self._register_task(reference, task)

            while True:
                event = await queue.get()
                adapted = _adapt(event)
                if adapted is not None:
                    yield adapted
                if isinstance(event, _TERMINAL_TYPES):
                    return
        except asyncio.CancelledError:
            # Tell the backend to wind the delegated task down and await its CANCELLED
            # confirmation (escalating to an interrupt if requested) before re-raising.
            # Bounded by the cancel timeout, so it can never hang the caller being torn down.
            if task is not None and queue is not None:
                await self._confirm_cancellation(
                    task,
                    queue,
                    escalate_to_interrupt,
                    cancel_timeout
                    if cancel_timeout is not None
                    else self.cancel_timeout,
                )
            raise
        except GeneratorExit:
            # Generator finalization (aclose): best-effort send only — awaiting event
            # delivery while the async generator is being torn down is fragile.
            if task is not None:
                try:
                    await self.agent.transport.asend(messages.CancelRequest(task=task))
                except Exception:
                    logger.warning(
                        "Failed to send CancelRequest for task %s", task, exc_info=True
                    )
            raise
        finally:
            self._pending_responses.pop(request.id, None)
            if task is not None:
                self._task_queues.pop(task, None)
                self._orphan_by_task.pop(task, None)
                self._last_seq.pop(task, None)
            self._reference_to_task.pop(reference, None)

    def _register_task(
        self, reference: str, task: str
    ) -> "asyncio.Queue[messages.ExecutionEvent]":
        """Bind ``reference`` → ``task`` and return the task's queue, draining any orphans."""
        self._reference_to_task[reference] = task
        queue = self._task_queues.setdefault(task, asyncio.Queue())
        for event in self._orphan_by_task.pop(task, []):
            queue.put_nowait(event)
        return queue

    async def _confirm_cancellation(
        self,
        task: str,
        queue: "asyncio.Queue[messages.ExecutionEvent]",
        escalate_to_interrupt: bool,
        timeout: float,
    ) -> None:
        """Cancel a delegated task and await its CANCELLED (or INTERRUPTED) mirror.

        Sends a ``CancelRequest``, then waits up to ``timeout`` for a
        ``CancelledEvent`` mirror. If that does not arrive and ``escalate_to_interrupt``
        is set, sends an ``InterruptRequest`` and waits for the ``InterruptedEvent``.
        Every wait is bounded, so this never hangs.
        """
        await self._send_control(messages.CancelRequest(task=task), task)
        if await self._await_terminal(queue, (messages.CancelledEvent,), timeout):
            return

        if not escalate_to_interrupt:
            logger.warning("Timed out awaiting CancelledEvent for task %s", task)
            return

        await self._send_control(messages.InterruptRequest(task=task), task)
        if not await self._await_terminal(
            queue, (messages.CancelledEvent, messages.InterruptedEvent), timeout
        ):
            logger.warning("Timed out awaiting InterruptedEvent for task %s", task)

    async def _send_control(
        self,
        request: "messages.CancelRequest | messages.InterruptRequest",
        task: str,
    ) -> None:
        """Send a lifecycle-control request over the socket (best-effort)."""
        try:
            await self.agent.transport.asend(request)
        except Exception:
            logger.warning(
                "Failed to send %s for task %s",
                type(request).__name__,
                task,
                exc_info=True,
            )

    async def _await_terminal(
        self,
        queue: "asyncio.Queue[messages.ExecutionEvent]",
        types: tuple[type["messages.ExecutionEvent"], ...],
        timeout: float,
    ) -> bool:
        """Drain ``queue`` until a mirror of one of ``types`` arrives.

        Bounded by ``timeout`` overall. Returns ``True`` if a matching mirror was
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
            if isinstance(event, types):
                return True

    # ------------------------------------------------------------------- inbound

    def handle_assign_response(self, message: messages.AssignResponse) -> None:
        """Resolve the waiting ``aassign`` with its ``AssignResponse``."""
        if message.task and not message.error:
            # Pre-create the queue and drain orphans so events that raced ahead of this
            # response are not lost (aassign reuses the same queue via setdefault).
            queue = self._task_queues.setdefault(message.task, asyncio.Queue())
            for event in self._orphan_by_task.pop(message.task, []):
                queue.put_nowait(event)
        future = self._pending_responses.get(message.request)
        if future is not None and not future.done():
            future.set_result(message)

    def handle_control_response(self, message: messages.ControlResponse) -> None:
        """Resolve a pending control request, if any (cancel is fire-and-forget by default)."""
        future = self._pending_control.get(message.request)
        if future is not None and not future.done():
            future.set_result(message)

    def handle_execution_event(self, message: messages.ExecutionEvent) -> None:
        """Route a task-event mirror to its task queue (buffering if the response is in flight)."""
        last = self._last_seq.get(message.task)
        if last is not None and message.seq <= last:
            logger.warning(
                "Out-of-order caller event for task %s: seq %s after %s",
                message.task,
                message.seq,
                last,
            )
        self._last_seq[message.task] = message.seq

        queue = self._task_queues.get(message.task)
        if queue is not None:
            queue.put_nowait(message)
        else:
            self._orphan_by_task.setdefault(message.task, []).append(message)

    # --------------------------------------------------------- protocol niceties

    async def __aenter__(self) -> "AgentPostman":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        return None
