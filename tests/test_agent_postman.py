"""Unit tests for the agent-as-caller postman (``rekuest_next.agents.caller``).

These exercise the translation/queueing logic with a fake transport — no backend. The
end-to-end behaviour (a real ``AssignResponse`` + mirror stream from the server) is covered
by the integration test ``tests/test_agent_caller.py``.
"""

import asyncio
from typing import List

import pytest

from rekuest_next import messages

from .memory_transport import MemoryAgentTransport
from rekuest_next.agents.caller import AgentPostman, CallerTaskEvent
from rekuest_next.api.schema import TaskEventKind
from rekuest_next.postmans.errors import AssignException
from rekuest_next.remote import _astream_raw
from rekuest_next.errors import ErrorCallError


def _call(**kwargs: object) -> dict:
    """The call description a postman is handed, with the defaults these tests share."""
    base = dict(
        args={"x": 1},
        reference="ref-1",
        hooks=None,
        parent=None,
        capture=False,
    )
    base.update(kwargs)
    return base


def _probe_call(**kwargs: object) -> dict:
    """The narrower call description a probe takes: no parent, no hooks, no capture."""
    base = dict(args={"x": 1}, reference="ref-1")
    base.update(kwargs)
    return base


async def _until(predicate, timeout: float = 1.0) -> None:
    """Yield control until ``predicate()`` is truthy (bounded)."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while not predicate():
        if loop.time() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0)


def _last_request(sink: MemoryAgentTransport) -> messages.AssignRequest:
    for msg in reversed(sink.sent):
        if isinstance(msg, messages.AssignRequest):
            return msg
    raise AssertionError("no AssignRequest was sent")


@pytest.mark.asyncio
async def test_aassign_emits_assign_request_with_field_mapping() -> None:
    """aassign translates the call description → AssignRequest, mapping the key fields."""
    sink = MemoryAgentTransport()
    pm = AgentPostman(sink)

    call = _call(dependency="dep-key", method="run", capture=True)
    out: List[CallerTaskEvent] = []

    async def consume() -> None:
        async for ev in pm.aassign(**call):
            out.append(ev)

    task = asyncio.create_task(consume())
    await _until(lambda: sink.sent)

    req = _last_request(sink)
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
    sink = MemoryAgentTransport()
    pm = AgentPostman(sink)
    out: List[CallerTaskEvent] = []

    async def consume() -> None:
        async for ev in pm.aassign(**_call()):
            out.append(ev)

    task = asyncio.create_task(consume())
    await _until(lambda: sink.sent)
    req = _last_request(sink)

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
    sink = MemoryAgentTransport()
    pm = AgentPostman(sink)

    async def consume() -> None:
        async for _ in pm.aassign(**_call()):
            pass

    task = asyncio.create_task(consume())
    await _until(lambda: sink.sent)
    req = _last_request(sink)

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
    sink = MemoryAgentTransport()
    pm = AgentPostman(sink)

    async def run() -> None:
        async for _ in _astream_raw(pm, **_call()):
            pass

    task = asyncio.create_task(run())
    await _until(lambda: sink.sent)
    req = _last_request(sink)

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
    sink = MemoryAgentTransport()
    pm = AgentPostman(sink)

    async def consume() -> None:
        async for _ in pm.aassign(**_call()):
            pass

    task = asyncio.create_task(consume())
    await _until(lambda: sink.sent)
    req = _last_request(sink)

    pm.handle_assign_response(
        messages.AssignResponse(request=req.id, reference=req.reference, task="t1")
    )
    # Let the generator reach the queue.get() await before cancelling.
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    cancels = [m for m in sink.sent if isinstance(m, messages.CancelRequest)]
    assert len(cancels) == 1
    assert cancels[0].task == "t1"


@pytest.mark.asyncio
async def test_concurrent_calls_do_not_cross_deliver() -> None:
    """Two simultaneous calls with distinct references/tasks stay isolated."""
    sink = MemoryAgentTransport()
    pm = AgentPostman(sink)
    out_a: List[CallerTaskEvent] = []
    out_b: List[CallerTaskEvent] = []

    async def consume(call, out) -> None:
        async for ev in pm.aassign(**call):
            out.append(ev)

    ta = asyncio.create_task(consume(_call(reference="ref-a"), out_a))
    tb = asyncio.create_task(consume(_call(reference="ref-b"), out_b))
    await _until(
        lambda: len(
            [m for m in sink.sent if isinstance(m, messages.AssignRequest)]
        )
        == 2
    )

    reqs = {
        m.reference: m
        for m in sink.sent
        if isinstance(m, messages.AssignRequest)
    }
    pm.handle_assign_response(
        messages.AssignResponse(request=reqs["ref-a"].id, reference="ref-a", task="ta")
    )
    pm.handle_assign_response(
        messages.AssignResponse(request=reqs["ref-b"].id, reference="ref-b", task="tb")
    )

    pm.handle_execution_event(
        messages.YieldEvent(task="tb", event="eb", seq=1, returns={"0": "B"})
    )
    pm.handle_execution_event(
        messages.YieldEvent(task="ta", event="ea", seq=1, returns={"0": "A"})
    )
    pm.handle_execution_event(messages.CompletedEvent(task="ta", event="ea2", seq=2))
    pm.handle_execution_event(messages.CompletedEvent(task="tb", event="eb2", seq=2))

    await asyncio.wait_for(asyncio.gather(ta, tb), timeout=1.0)
    assert out_a[0].returns == {"0": "A"}
    assert out_b[0].returns == {"0": "B"}



@pytest.mark.asyncio
async def test_aprobe_fires_a_probe_and_streams_its_events() -> None:
    """A probe is originated and streamed exactly like an assign, keyed by the probe id.

    Probes are ephemeral: zero persistence, no history, no task tree. The backend answers
    with a ``probe`` id rather than a durable ``task`` id, and the event mirrors are keyed
    by that id — which is the only difference the caller sees.
    """
    sink = MemoryAgentTransport()
    pm = AgentPostman(sink)

    out: List[CallerTaskEvent] = []

    async def consume() -> None:
        async for event in pm.aprobe(**_probe_call()):
            out.append(event)

    task = asyncio.create_task(consume())

    await _until(lambda: any(isinstance(m, messages.ProbeRequest) for m in sink.sent))
    request = next(m for m in sink.sent if isinstance(m, messages.ProbeRequest))
    assert request.args == {"x": 1}
    assert request.reference == "ref-1"

    pm.handle_probe_response(messages.ProbeResponse(request=request.id, probe="p-1"))
    pm.handle_execution_event(
        messages.YieldEvent(task="p-1", event="e-1", seq=1, returns={"0": "ok"})
    )
    pm.handle_execution_event(messages.CompletedEvent(task="p-1", event="e-2", seq=2))

    await asyncio.wait_for(task, timeout=1.0)
    assert [e.kind for e in out] == [TaskEventKind.YIELD, TaskEventKind.COMPLETED]
    assert out[0].returns == {"0": "ok"}


@pytest.mark.asyncio
async def test_aprobe_surfaces_a_refusal() -> None:
    """A probe against an action that did not declare allowProbe is refused."""
    sink = MemoryAgentTransport()
    pm = AgentPostman(sink)

    async def consume() -> None:
        async for _ in pm.aprobe(**_probe_call()):
            pass

    task = asyncio.create_task(consume())
    await _until(lambda: any(isinstance(m, messages.ProbeRequest) for m in sink.sent))
    request = next(m for m in sink.sent if isinstance(m, messages.ProbeRequest))

    pm.handle_probe_response(
        messages.ProbeResponse(request=request.id, error="allow_probe not declared")
    )

    with pytest.raises(AssignException, match="allow_probe"):
        await asyncio.wait_for(task, timeout=1.0)
