"""Unit tests for the agent-as-caller postman (``rekuest_next.agents.caller``).

These exercise the translation/queueing logic with a fake transport — no backend. The
end-to-end behaviour (a real ``AssignResponse`` + mirror stream from the server) is covered
by the integration test ``tests/integration/test_agent_caller.py``.
"""

import asyncio
from typing import List

import pytest

from rekuest_next import messages
from rekuest_next.agents.caller import AgentPostman, CallerTaskEvent
from rekuest_next.api.schema import TaskEventKind
from rekuest_next.postmans.errors import AssignException
from rekuest_next.remote import _astream_raw, _build_assign_input
from rekuest_next.errors import ErrorCallError


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


def _assign(**kwargs: object):
    """Build a valid AssignInput via the same helper remote.py uses."""
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


async def _until(predicate, timeout: float = 1.0) -> None:
    """Yield control until ``predicate()`` is truthy (bounded)."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while not predicate():
        if loop.time() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0)


def _last_request(agent: FakeAgent) -> messages.AssignRequest:
    for msg in reversed(agent.transport.sent):
        if isinstance(msg, messages.AssignRequest):
            return msg
    raise AssertionError("no AssignRequest was sent")


@pytest.mark.asyncio
async def test_aassign_emits_assign_request_with_field_mapping() -> None:
    """aassign translates AssignInput → AssignRequest, mapping the key fields."""
    agent = FakeAgent()
    pm = AgentPostman(agent)

    assign = _assign(dependency="dep-key", method="run", capture=True)
    out: List[CallerTaskEvent] = []

    async def consume() -> None:
        async for ev in pm.aassign(assign):
            out.append(ev)

    task = asyncio.create_task(consume())
    await _until(lambda: agent.transport.sent)

    req = _last_request(agent)
    assert req.reference == "ref-1"
    assert req.args == {"x": 1}
    assert req.dependency == "dep-key"
    assert req.method == "run"
    assert req.capture is True
    assert req.parent is None

    pm.handle_assign_response(
        messages.AssignResponse(request=req.id, reference=req.reference, task="t1")
    )
    pm.handle_execution_event(
        messages.YieldEvent(task="t1", event="e1", seq=1, returns={"0": 5})
    )
    pm.handle_execution_event(messages.CompletedEvent(task="t1", event="e2", seq=2))

    await asyncio.wait_for(task, timeout=1.0)

    kinds = [e.kind for e in out]
    assert kinds == [TaskEventKind.YIELD, TaskEventKind.COMPLETED]
    assert out[0].returns == {"0": 5}


@pytest.mark.asyncio
async def test_event_before_response_is_buffered() -> None:
    """A mirror that races ahead of the AssignResponse is still delivered (orphan buffer)."""
    agent = FakeAgent()
    pm = AgentPostman(agent)
    out: List[CallerTaskEvent] = []

    async def consume() -> None:
        async for ev in pm.aassign(_assign()):
            out.append(ev)

    task = asyncio.create_task(consume())
    await _until(lambda: agent.transport.sent)
    req = _last_request(agent)

    # Yield arrives BEFORE we route reference -> task.
    pm.handle_execution_event(
        messages.YieldEvent(task="t1", event="e1", seq=1, returns={"0": 9})
    )
    pm.handle_assign_response(
        messages.AssignResponse(request=req.id, reference=req.reference, task="t1")
    )
    pm.handle_execution_event(messages.CompletedEvent(task="t1", event="e2", seq=2))

    await asyncio.wait_for(task, timeout=1.0)
    assert out[0].returns == {"0": 9}


@pytest.mark.asyncio
async def test_nack_raises_assign_exception() -> None:
    """An AssignResponse carrying an error makes aassign raise."""
    agent = FakeAgent()
    pm = AgentPostman(agent)

    async def consume() -> None:
        async for _ in pm.aassign(_assign()):
            pass

    task = asyncio.create_task(consume())
    await _until(lambda: agent.transport.sent)
    req = _last_request(agent)

    pm.handle_assign_response(
        messages.AssignResponse(
            request=req.id,
            reference=req.reference,
            task=None,
            created=False,
            error="missing can_assign_root",
        )
    )

    with pytest.raises(AssignException, match="can_assign_root"):
        await asyncio.wait_for(task, timeout=1.0)


@pytest.mark.asyncio
async def test_failed_event_raises_error_call_error_through_stream() -> None:
    """A FailedEvent surfaces as ErrorCallError via remote._astream_raw (the real seam)."""
    agent = FakeAgent()
    pm = AgentPostman(agent)
    assign = _assign()

    async def run() -> None:
        async for _ in _astream_raw(pm, assign):
            pass

    task = asyncio.create_task(run())
    await _until(lambda: agent.transport.sent)
    req = _last_request(agent)

    pm.handle_assign_response(
        messages.AssignResponse(request=req.id, reference=req.reference, task="t1")
    )
    pm.handle_execution_event(
        messages.FailedEvent(task="t1", event="e1", seq=1, error="boom")
    )

    with pytest.raises(ErrorCallError, match="boom"):
        await asyncio.wait_for(task, timeout=1.0)


@pytest.mark.asyncio
async def test_cancellation_sends_cancel_request() -> None:
    """Cancelling an in-flight aassign sends a best-effort CancelRequest for the task."""
    agent = FakeAgent()
    pm = AgentPostman(agent)

    async def consume() -> None:
        async for _ in pm.aassign(_assign()):
            pass

    task = asyncio.create_task(consume())
    await _until(lambda: agent.transport.sent)
    req = _last_request(agent)

    pm.handle_assign_response(
        messages.AssignResponse(request=req.id, reference=req.reference, task="t1")
    )
    # Let the generator reach the queue.get() await before cancelling.
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    cancels = [m for m in agent.transport.sent if isinstance(m, messages.CancelRequest)]
    assert len(cancels) == 1
    assert cancels[0].task == "t1"


@pytest.mark.asyncio
async def test_concurrent_calls_do_not_cross_deliver() -> None:
    """Two simultaneous calls with distinct references/tasks stay isolated."""
    agent = FakeAgent()
    pm = AgentPostman(agent)
    out_a: List[CallerTaskEvent] = []
    out_b: List[CallerTaskEvent] = []

    async def consume(assign, out) -> None:
        async for ev in pm.aassign(assign):
            out.append(ev)

    ta = asyncio.create_task(consume(_assign(reference="ref-a"), out_a))
    tb = asyncio.create_task(consume(_assign(reference="ref-b"), out_b))
    await _until(lambda: len([m for m in agent.transport.sent if isinstance(m, messages.AssignRequest)]) == 2)

    reqs = {m.reference: m for m in agent.transport.sent if isinstance(m, messages.AssignRequest)}
    pm.handle_assign_response(messages.AssignResponse(request=reqs["ref-a"].id, reference="ref-a", task="ta"))
    pm.handle_assign_response(messages.AssignResponse(request=reqs["ref-b"].id, reference="ref-b", task="tb"))

    pm.handle_execution_event(messages.YieldEvent(task="tb", event="eb", seq=1, returns={"0": "B"}))
    pm.handle_execution_event(messages.YieldEvent(task="ta", event="ea", seq=1, returns={"0": "A"}))
    pm.handle_execution_event(messages.CompletedEvent(task="ta", event="ea2", seq=2))
    pm.handle_execution_event(messages.CompletedEvent(task="tb", event="eb2", seq=2))

    await asyncio.wait_for(asyncio.gather(ta, tb), timeout=1.0)
    assert out_a[0].returns == {"0": "A"}
    assert out_b[0].returns == {"0": "B"}


def test_transport_mode_defaults_executor_and_is_configurable() -> None:
    """The websocket transport exposes a configurable register mode (default EXECUTOR)."""
    from rekuest_next.agents.transport.websocket import WebsocketAgentTransport

    async def loader() -> str:
        return "tok"

    default = WebsocketAgentTransport(endpoint_url="ws://x/agi", token_loader=loader)
    assert default.mode == messages.AgentMode.EXECUTOR

    orchestrator = WebsocketAgentTransport(
        endpoint_url="ws://x/agi",
        token_loader=loader,
        mode=messages.AgentMode.ORCHESTRATOR,
    )
    register = messages.Register(token="tok", mode=orchestrator.mode)
    # Register uses use_enum_values, so the value is the wire string.
    assert register.mode == "ORCHESTRATOR"
