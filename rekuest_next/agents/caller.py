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

- outbound: the call description (:meth:`Postman.aassign`'s arguments) → an
  ``AssignRequest`` socket message; ``reference`` is reused as the idempotency key.
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
from typing import Any, AsyncGenerator, Dict, List, Optional, Sequence

from rath.scalars import ID

from rekuest_next import messages
from rekuest_next.api.schema import HookInput, TaskEventKind
from rekuest_next.agents.transport.types import MessageSink
from rekuest_next.postmans.errors import AssignException
from rekuest_next.scalars import ActionHash

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


#: Mirror message types that end a delegated task's stream. Every other mirror
#: (Bound/Queued/Started/Progress/Log/Delegate/Disconnected/…ing/…ed) is consumed for
#: bookkeeping only — ``_astream_raw`` would ignore it anyway. Defined alongside the
#: reports it mirrors in :mod:`rekuest_next.messages`.
_TERMINAL_TYPES = messages.TERMINAL_EVENT_MIRRORS


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


def _response_id(
    response: "messages.AssignResponse | messages.ProbeResponse",
) -> Optional[str]:
    """The id the backend assigned, whichever kind of answer this is.

    An assign is answered with a durable ``task`` id; a probe with an ephemeral ``probe``
    id (``p-…``). Everything downstream — the event queues, cancellation, cleanup — keys
    off this one value, which is why the two flows can share a single path.
    """
    if isinstance(response, messages.ProbeResponse):
        return response.probe
    return response.task


class AgentPostman:
    """A :class:`Postman` that originates work over the agent's socket.

    A single instance is shared by every actor on the agent; all per-call state is keyed by
    request id / task id, so concurrent calls never collide. It depends only on a
    :class:`~rekuest_next.agents.transport.types.MessageSink` — somewhere to put a
    message — rather than on the agent, so it cannot reach past the socket it was given.
    """

    def __init__(self, sink: MessageSink, cancel_timeout: float = 5.0) -> None:
        self.sink = sink
        # Max seconds to await a CANCELLED/INTERRUPTED confirmation when an assign
        # stream is cancelled. Bounds cancellation so it can never hang.
        self.cancel_timeout = cancel_timeout
        # request id -> future resolved with the AssignResponse or ProbeResponse
        self._pending_responses: Dict[
            str,
            "asyncio.Future[messages.AssignResponse | messages.ProbeResponse]",
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
        """Whether work can currently be originated over the socket."""
        return self.sink.connected

    # ------------------------------------------------------------------ outbound

    async def aassign(  # noqa: PLR0913 - the call description, mirrored from the protocol
        self,
        *,
        args: Dict[str, Any],
        capture: bool = False,
        reference: Optional[str] = None,
        hooks: Optional[Sequence[HookInput]] = None,
        action: Optional[ID] = None,
        implementation: Optional[ID] = None,
        parent: Optional[ID] = None,
        dependency: Optional[str] = None,
        method: Optional[str] = None,
        action_hash: Optional[ActionHash] = None,
        agent: Optional[ID] = None,
        interface: Optional[str] = None,
        resolution: Optional[ID] = None,
        step: Optional[bool] = None,
        escalate_to_interrupt: bool = False,
        cancel_timeout: Optional[float] = None,
    ) -> AsyncGenerator[CallerTaskEvent, None]:
        """Originate a task over the agent socket and stream its events.

        See :meth:`rekuest_next.postmans.types.Postman.aassign`. Unlike the GraphQL
        mutation, the socket carries the whole task tree, so ``parent`` / ``dependency``
        / ``method`` are sent as given — that is the reason actor-internal calls route
        here at all.

        Sends an ``AssignRequest``, awaits the ``AssignResponse`` (to learn the durable task
        id), then yields a ``CallerTaskEvent`` for every surfaced mirror until a terminal one
        arrives. On cancellation a ``CancelRequest`` is sent and the ``CancelledEvent``
        confirmation is awaited (bounded by ``cancel_timeout``); if ``escalate_to_interrupt``
        is set and the cancel is not confirmed in time, an ``InterruptRequest`` follows.
        """
        request_reference = reference or str(uuid.uuid4())
        request = messages.AssignRequest(
            reference=request_reference,
            args=dict(args or {}),
            action=action,
            action_hash=action_hash,
            implementation=implementation,
            agent=agent,
            interface=interface,
            parent=parent,
            dependency=dependency,
            method=method,
            resolution=resolution,
            hooks=[h.model_dump(by_alias=True) for h in (hooks or [])],
            capture=capture,
            step=step,
        )
        async for event in self._astream(
            request,
            request_reference,
            escalate_to_interrupt,
            cancel_timeout,
        ):
            yield event

    async def aprobe(
        self,
        *,
        args: Dict[str, Any],
        reference: Optional[str] = None,
        action: Optional[ID] = None,
        implementation: Optional[ID] = None,
        action_hash: Optional[ActionHash] = None,
        escalate_to_interrupt: bool = False,
        cancel_timeout: Optional[float] = None,
    ) -> AsyncGenerator[CallerTaskEvent, None]:
        """Fire a probe over the agent socket and stream its events.

        A probe is an ephemeral, zero-persistence invocation under this agent's own
        identity: no server-side history, no replay or recovery, and no task tree — probes
        are always provenance roots. Only actions declaring ``allowProbe`` accept one.

        It therefore takes a narrower call description than :meth:`aassign`: no parent, no
        dependency resolution and no hooks, because none of them can apply.

        The event stream is shaped exactly like :meth:`aassign`'s; the id it is keyed by is
        the probe id (``p-…``) rather than a durable task id. Resends are *not* idempotent:
        there is no durable row to dedupe against, so a resend after a lost response fires a
        new probe.
        """
        request_reference = reference or str(uuid.uuid4())
        request = messages.ProbeRequest(
            reference=request_reference,
            args=dict(args or {}),
            action=action,
            action_hash=action_hash,
            implementation=implementation,
        )
        async for event in self._astream(
            request,
            request_reference,
            escalate_to_interrupt,
            cancel_timeout,
        ):
            yield event

    async def _astream(
        self,
        request: "messages.AssignRequest | messages.ProbeRequest",
        reference: str,
        escalate_to_interrupt: bool,
        cancel_timeout: Optional[float],
    ) -> AsyncGenerator[CallerTaskEvent, None]:
        """Send one origination request and stream the resulting events until terminal.

        Shared by assigns and probes: the two differ only in which request goes out and
        which field of the answer carries the id, so the correlation, cancellation and
        cleanup below are identical for both.
        """
        loop = asyncio.get_event_loop()
        response_future: (
            "asyncio.Future[messages.AssignResponse | messages.ProbeResponse]"
        ) = loop.create_future()
        self._pending_responses[request.id] = response_future

        task: Optional[str] = None
        queue: Optional["asyncio.Queue[messages.ExecutionEvent]"] = None
        try:
            await self.sink.asend(request)
            response = await response_future

            if response.error:
                raise AssignException(response.error)
            task = _response_id(response)
            if not task:
                raise AssignException(
                    "The backend acked the request without an id and without an error."
                )

            queue = self._register_task(reference, task)

            while True:
                event = await queue.get()
                adapted = _adapt(event)
                if adapted is not None:
                    yield adapted
                if isinstance(event, _TERMINAL_TYPES):
                    return
        except asyncio.CancelledError:
            # Tell the backend to wind the delegated work down and await its CANCELLED
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
                await self._send_control(messages.CancelRequest(task=task), task)
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
            await self.sink.asend(request)
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

    def handle_probe_response(self, message: messages.ProbeResponse) -> None:
        """Resolve the waiting ``aprobe`` with its ``ProbeResponse``."""
        if message.probe and not message.error:
            # Pre-create the queue and drain orphans so events that raced ahead of this
            # response are not lost (the stream reuses the same queue via setdefault).
            queue = self._task_queues.setdefault(message.probe, asyncio.Queue())
            for event in self._orphan_by_task.pop(message.probe, []):
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
