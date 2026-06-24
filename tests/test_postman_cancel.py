"""Focused, backend-free tests for postman cancel-confirmation + escalation.

Cancelling a call through any postman should send the cancel and then *await* the
backend's CANCELLED confirmation before re-raising (bounded by ``cancel_timeout``),
and — when ``escalate_to_interrupt`` is set — escalate to a forceful interrupt if the
graceful cancel is not confirmed in time. These tests drive that machinery directly
with hand-written test doubles (no mocks, no socket/GraphQL backend):

- ``GraphQLPostman``: a recording subclass overrides the ``acancel``/``ainterrupt``
  send seams, and ``_confirm_cancellation`` is driven against a real ``asyncio.Queue``.
- ``AgentPostman``: the full ``aassign`` is exercised over a ``FakeTransport`` and an
  ``asyncio.Task`` is cancelled, with confirmation mirrors fed back in.
- ``remote.aiterate_raw``: a recording postman asserts both flags are threaded through.
"""

import asyncio
from datetime import datetime, timezone
from types import TracebackType
from typing import Any, AsyncGenerator, Callable, List, Optional, Tuple

import pytest
from pydantic import PrivateAttr

from rekuest_next import messages
from rekuest_next.agents.caller import AgentPostman
from rekuest_next.api.schema import AssignInput, TaskEventChange, TaskEventKind
from rekuest_next.postmans.graphql import GraphQLPostman
from rekuest_next.rath import RekuestNextRath
from rekuest_next.remote import _build_assign_input, aiterate_raw

from rath.links.testing.direct_succeeding_link import DirectSucceedingLink


# --------------------------------------------------------------------------- helpers


async def _until(predicate: Callable[[], object], timeout: float = 1.0) -> None:
    """Yield control until ``predicate()`` is truthy (bounded)."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while not predicate():
        if loop.time() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0)


def _change(kind: TaskEventKind, task: str = "t1") -> TaskEventChange:
    """Build a slim change-feed event of a given kind."""
    return TaskEventChange(
        id=f"e-{kind.value}",
        task=task,
        kind=kind,
        createdAt=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------- GraphQLPostman tests


class RecordingGraphQLPostman(GraphQLPostman):
    """A ``GraphQLPostman`` that records cancel/interrupt sends instead of hitting GraphQL."""

    _cancels: List[str] = PrivateAttr(default_factory=lambda: [])
    _interrupts: List[str] = PrivateAttr(default_factory=lambda: [])

    async def _send_cancel(self, task_id: str, timeout: float) -> None:
        self._cancels.append(task_id)

    async def _send_interrupt(self, task_id: str, timeout: float) -> None:
        self._interrupts.append(task_id)


def _graphql_postman() -> RecordingGraphQLPostman:
    return RecordingGraphQLPostman(rath=RekuestNextRath(link=DirectSucceedingLink()))


@pytest.mark.asyncio
async def test_graphql_awaits_cancelled_before_returning() -> None:
    """_confirm_cancellation sends the cancel and only returns once CANCELLED arrives."""
    pm = _graphql_postman()
    queue: "asyncio.Queue[TaskEventChange]" = asyncio.Queue()

    confirm = asyncio.create_task(
        pm._confirm_cancellation("t1", queue, escalate_to_interrupt=False, timeout=1.0)
    )

    # The cancel goes out immediately, but the coroutine must keep waiting for the
    # CANCELLED confirmation before completing.
    await _until(lambda: pm._cancels == ["t1"])
    await asyncio.sleep(0)
    assert not confirm.done(), "returned before the CANCELLED event was delivered"

    queue.put_nowait(_change(TaskEventKind.CANCELLED))
    await asyncio.wait_for(confirm, timeout=1.0)

    assert pm._cancels == ["t1"]
    assert pm._interrupts == []
    assert queue.empty()


@pytest.mark.asyncio
async def test_graphql_escalates_to_interrupt_on_timeout() -> None:
    """When CANCELLED never arrives and escalation is on, an interrupt is sent."""
    pm = _graphql_postman()
    queue: "asyncio.Queue[TaskEventChange]" = asyncio.Queue()

    confirm = asyncio.create_task(
        pm._confirm_cancellation("t1", queue, escalate_to_interrupt=True, timeout=0.05)
    )

    # Cancel goes out, times out (no CANCELLED), then escalates to interrupt.
    await _until(lambda: pm._interrupts == ["t1"])
    assert pm._cancels == ["t1"]

    queue.put_nowait(_change(TaskEventKind.INTERRUPTED))
    await asyncio.wait_for(confirm, timeout=1.0)


@pytest.mark.asyncio
async def test_graphql_no_escalation_when_disabled() -> None:
    """Without escalation, a cancel timeout returns without sending an interrupt."""
    pm = _graphql_postman()
    queue: "asyncio.Queue[TaskEventChange]" = asyncio.Queue()

    await asyncio.wait_for(
        pm._confirm_cancellation(
            "t1", queue, escalate_to_interrupt=False, timeout=0.05
        ),
        timeout=1.0,
    )

    assert pm._cancels == ["t1"]
    assert pm._interrupts == []


# ------------------------------------------------------------------ AgentPostman tests


class FakeTransport:
    """Records every outbound message instead of touching a socket."""

    connected = True

    def __init__(self) -> None:
        self.sent: List[messages.FromAgentMessage] = []

    async def asend(self, message: messages.FromAgentMessage) -> None:
        self.sent.append(message)


class FakeAgent:
    def __init__(self) -> None:
        self.transport = FakeTransport()


def _assign(**kwargs: object) -> AssignInput:
    base = dict(
        args={"x": 1},
        reference="ref-1",
        hooks=None,
        parent=None,
        cached=False,
        log=False,
        capture=False,
    )
    base.update(kwargs)
    return _build_assign_input(**base)  # type: ignore[arg-type]


def _last_request(agent: FakeAgent) -> messages.AssignRequest:
    for msg in reversed(agent.transport.sent):
        if isinstance(msg, messages.AssignRequest):
            return msg
    raise AssertionError("no AssignRequest was sent")


def _has(agent: FakeAgent, typ: type) -> bool:
    return any(isinstance(m, typ) for m in agent.transport.sent)


async def _start_and_assign(
    pm: AgentPostman, agent: FakeAgent, escalate_to_interrupt: bool = False
) -> "asyncio.Task[None]":
    """Start aassign, deliver the AssignResponse, and drive it into its event loop.

    A sentinel YieldEvent is delivered and we wait until ``aassign`` has consumed it,
    which proves the generator has bound its task/queue and is parked on ``queue.get()``
    — so a subsequent ``task.cancel()`` exercises the confirmation path (rather than
    racing the not-yet-started loop).
    """
    out: List[Any] = []

    async def consume() -> None:
        async for ev in pm.aassign(
            _assign(), escalate_to_interrupt=escalate_to_interrupt
        ):
            out.append(ev)

    task = asyncio.create_task(consume())
    await _until(lambda: agent.transport.sent)
    req = _last_request(agent)
    pm.handle_assign_response(
        messages.AssignResponse(request=req.id, reference=req.reference, task="t1")
    )
    pm.handle_execution_event(
        messages.YieldEvent(task="t1", event="e0", seq=1, returns={"0": 1})
    )
    await _until(lambda: out)  # the loop is now running and parked on queue.get()
    return task


@pytest.mark.asyncio
async def test_agent_awaits_cancelled_before_reraising() -> None:
    """aassign sends a CancelRequest and awaits the CancelledEvent before re-raising."""
    agent = FakeAgent()
    pm = AgentPostman(agent, cancel_timeout=1.0)

    task = await _start_and_assign(pm, agent)
    task.cancel()

    await _until(lambda: _has(agent, messages.CancelRequest))
    await asyncio.sleep(0)
    assert not task.done(), "re-raised before awaiting the CancelledEvent"

    pm.handle_execution_event(messages.CancelledEvent(task="t1", event="e1", seq=2))
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=1.0)

    assert _has(agent, messages.CancelRequest)
    assert not _has(agent, messages.InterruptRequest)


@pytest.mark.asyncio
async def test_agent_escalates_to_interrupt_on_timeout() -> None:
    """With escalation on, an unconfirmed cancel is followed by an InterruptRequest."""
    agent = FakeAgent()
    pm = AgentPostman(agent, cancel_timeout=0.05)

    task = await _start_and_assign(pm, agent, escalate_to_interrupt=True)
    task.cancel()

    await _until(lambda: _has(agent, messages.InterruptRequest))
    assert _has(agent, messages.CancelRequest)

    pm.handle_execution_event(messages.InterruptedEvent(task="t1", event="e2", seq=3))
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=1.0)


@pytest.mark.asyncio
async def test_agent_no_escalation_when_disabled() -> None:
    """Without escalation, a cancel timeout re-raises without sending an interrupt."""
    agent = FakeAgent()
    pm = AgentPostman(agent, cancel_timeout=0.05)

    task = await _start_and_assign(pm, agent)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=1.0)

    assert _has(agent, messages.CancelRequest)
    assert not _has(agent, messages.InterruptRequest)


# ------------------------------------------------------------- remote threading test


class RecordingPostman:
    """A minimal Postman that records the cancel-control kwargs it is called with."""

    connected = True

    def __init__(self) -> None:
        self.calls: List[Tuple[bool, Optional[float]]] = []

    async def aassign(
        self,
        assign: AssignInput,  # noqa: ARG002 - part of the Postman protocol
        escalate_to_interrupt: bool = False,
        cancel_timeout: Optional[float] = None,
    ) -> AsyncGenerator[TaskEventChange, None]:
        self.calls.append((escalate_to_interrupt, cancel_timeout))
        yield _change(TaskEventKind.COMPLETED)

    async def __aenter__(self) -> "RecordingPostman":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        return None


@pytest.mark.asyncio
async def test_remote_threads_cancel_params_to_postman() -> None:
    """aiterate_raw forwards escalate_to_interrupt and cancel_timeout to the postman."""
    pm = RecordingPostman()

    async for _ in aiterate_raw(
        kwargs={},
        postman=pm,
        escalate_to_interrupt=True,
        cancel_timeout=2.5,
    ):
        pass

    assert pm.calls == [(True, 2.5)]
