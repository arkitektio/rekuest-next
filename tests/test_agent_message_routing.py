"""No-Docker checks for what the agent does with each inbound message.

These run a real ``BaseAgent`` message loop against
:class:`tests.memory_transport.MemoryAgentTransport`, which is the first fake able to
drive it (the pre-existing ones had no ``areceive``). That is what makes the routing in
``BaseAgent.process`` testable rather than merely inspectable.
"""

import asyncio
import json
from typing import AsyncIterator, List

import pytest

from rekuest_next import messages
from rekuest_next.agents.base import BaseAgent
from rekuest_next.app import AppRegistry
from rekuest_next.agents.hooks.registry import StartupHookReturns

from rekuest_next.agents.errors import AgentException

from .memory_transport import MemoryAgentTransport


@pytest.fixture()
def transport() -> MemoryAgentTransport:
    return MemoryAgentTransport()


@pytest.fixture()
def agent(transport: MemoryAgentTransport) -> BaseAgent:
    """A bare agent with its own registry, so nothing leaks between tests."""
    return BaseAgent(
        name="routing-test", transport=transport, app_registry=AppRegistry()
    )


async def _run_loop(agent: BaseAgent) -> AsyncIterator[None]:
    """Drive process() over the transport stream, as aloop does."""
    async for message in agent.transport.areceive():
        await agent.process(message)
        yield


async def _pump(agent: BaseAgent, count: int) -> None:
    """Process exactly `count` inbound messages."""
    loop = _run_loop(agent)
    for _ in range(count):
        await asyncio.wait_for(loop.__anext__(), timeout=2.0)


def _errors(transport: MemoryAgentTransport) -> List[str]:
    return [c.error for c in transport.of_type(messages.Critical)]


@pytest.mark.asyncio
async def test_interrupt_for_an_unknown_task_does_not_kill_the_agent(
    agent: BaseAgent, transport: MemoryAgentTransport
) -> None:
    """An Interrupt used to reach process()'s `else` and raise AgentException.

    That exception unwinds the message consumer and tears the whole agent down, so a
    single interrupt escalation against this agent would take the process's other work
    with it. ``escalate_to_interrupt`` is public API all through ``remote.py``, and
    ``Interrupted`` was already listed as a terminal report the agent retains -- so the
    report path was designed and only the inbound half was missing.
    """
    transport.feed(messages.Interrupt(task="not-a-task"))

    await _pump(agent, 1)

    # It degrades exactly as Cancel does for an unknown task: a Critical, not a crash.
    assert _errors(transport), "an unknown task should be reported, not raised"


@pytest.mark.asyncio
async def test_interrupt_reaches_the_actor_and_reports_interrupted(
    agent: BaseAgent, transport: MemoryAgentTransport
) -> None:
    """A running task is stopped and reported as Interrupted, mirroring Cancel."""
    started = asyncio.Event()

    def slow(x: int) -> int:
        """A function that blocks so there is something to interrupt."""
        raise NotImplementedError

    async def aslow(x: int) -> int:
        """Block until interrupted."""
        started.set()
        await asyncio.sleep(60)
        return x

    from rekuest_next.register import register

    register(
        aslow,
        implementation_registry=agent.app_registry,
        structure_registry=agent.app_registry.structure_registry,
    )
    agent.collect_from_registry()

    assign = messages.Assign(
        task="task-1",
        interface="aslow",
        args={"x": 1},
        implementation="impl-1",
        action="action-1",
        reference="ref-1",
        user="user-1",
        org="org-1",
    )
    transport.feed(assign)
    await _pump(agent, 1)
    await asyncio.wait_for(started.wait(), timeout=2.0)

    assert agent.running_assignments.get("task-1"), (
        "the agent should record which actor is running the task"
    )

    transport.feed(messages.Interrupt(task="task-1"))
    await _pump(agent, 1)

    interrupted = transport.of_type(messages.Interrupted)
    assert interrupted, f"expected an Interrupted report, got {transport.sent}"
    assert interrupted[0].task == "task-1"
    assert "task-1" not in agent.running_assignments, (
        "a terminal report must clear the running-assignment record"
    )


@pytest.mark.asyncio
async def test_init_releases_connect_and_resends_unacked_reports(
    agent: BaseAgent, transport: MemoryAgentTransport
) -> None:
    """Init is the session signal: it acknowledges Register and replays retained reports.

    The backend re-sends Init on every connection, so this is also the only notice the
    agent gets that a dropped connection was recovered -- which is why the persist-then-ack
    replay hangs off it.
    """
    # A terminal report goes out and is retained until the backend acks it.
    await agent._adispatch(messages.Completed(task="task-1", returns={}))
    completed = transport.of_type(messages.Completed)
    assert len(completed) == 1
    assert agent._unacked_events, "a terminal report must be retained pending its ack"

    transport.feed(messages.Init(agent="agent-1"))
    await _pump(agent, 1)

    assert agent._connected_event.is_set(), "Init must release anyone awaiting aconnect"
    resent = transport.of_type(messages.Completed)
    assert len(resent) == 2, "the unacked report must be resent on the new connection"
    assert resent[1].seq == resent[0].seq, (
        "the resend must preserve the original seq, not be re-stamped"
    )

    # Once acked it is dropped, so a later Init does not replay it again.
    transport.feed(messages.EventAck(event=completed[0].id))
    await _pump(agent, 1)
    assert not agent._unacked_events

    transport.feed(messages.Init(agent="agent-1"))
    await _pump(agent, 1)
    assert len(transport.of_type(messages.Completed)) == 2, (
        "an acked report must not replay"
    )


@pytest.mark.asyncio
async def test_seq_is_monotonic_across_reports(
    agent: BaseAgent, transport: MemoryAgentTransport
) -> None:
    """Every agent->backend event gets a strictly increasing stream seq."""
    for i in range(4):
        await agent._adispatch(messages.Progress(task="t", message=f"{i}", progress=i))

    seqs = [p.seq for p in transport.of_type(messages.Progress)]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs), seqs


@pytest.mark.asyncio
async def test_caller_answers_go_to_the_postman_not_the_actors(
    agent: BaseAgent, transport: MemoryAgentTransport
) -> None:
    """Answers to delegated work are a different concern from assigned work.

    They are keyed by the caller's request id and must never be looked up in
    managed_assignments, which only ever holds work assigned *to* this agent.
    """
    seen: List[messages.ExecutionEvent] = []
    agent.caller_postman.handle_execution_event = seen.append  # type: ignore[method-assign]

    transport.feed(messages.CompletedEvent(task="delegated-1", event="ev-1", seq=1))
    await _pump(agent, 1)

    assert len(seen) == 1, "an execution-event mirror belongs to the caller postman"
    assert "delegated-1" not in agent.managed_assignments


@pytest.mark.asyncio
async def test_lock_transitions_are_reported_to_the_backend(
    agent: BaseAgent, transport: MemoryAgentTransport
) -> None:
    """Every agent reports locks now, not just the FastAPI one.

    These were silent no-ops on ``BaseAgent``, so a RekuestAgent acquiring a lock told the
    backend nothing. NOTE: no integration test acquires a lock, so this emission is
    covered here but not against a real server.
    """
    await agent.alock("mylock", "task-1")
    await agent.aunlock("mylock")

    locks = transport.of_type(messages.Lock)
    unlocks = transport.of_type(messages.Unlock)
    assert [(m.key, m.task) for m in locks] == [("mylock", "task-1")]
    assert [m.key for m in unlocks] == ["mylock"]


@pytest.mark.asyncio
async def test_lock_reporting_survives_a_dead_socket(agent: BaseAgent) -> None:
    """A lock must stay acquirable when the backend cannot be told about it.

    Mutual exclusion comes from the local TaskLock, so a failed report is logged rather
    than raised -- otherwise an unreachable backend would stop the app from running work
    it can serialise perfectly well on its own.
    """

    agent.transport = _DeadSocket()

    # Must not raise.
    await agent.alock("mylock", "task-1")
    await agent.aunlock("mylock")


class _DeadSocket(MemoryAgentTransport):
    """A transport whose socket has gone away underneath it."""

    async def asend(self, message: messages.FromAgentMessage) -> None:
        """Fail the way a lost connection does."""
        raise ConnectionResetError("socket is gone")


@pytest.mark.asyncio
async def test_teardown_cancels_in_flight_actor_work(
    agent: BaseAgent, transport: MemoryAgentTransport
) -> None:
    """Assignments must not outlive the agent that owns them.

    Teardown used to loop over a ``managed_actor_tasks`` dict that was never populated,
    so in-flight work was abandoned mid-flight and the backend never heard about it.
    """
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def blocker(x: int) -> int:
        """Run until cancelled, recording that it was."""
        started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return x

    from rekuest_next.register import register

    register(
        blocker,
        implementation_registry=agent.app_registry,
        structure_registry=agent.app_registry.structure_registry,
    )
    agent.collect_from_registry()

    transport.feed(
        messages.Assign(
            task="task-1",
            interface="blocker",
            args={"x": 1},
            implementation="impl-1",
            action="action-1",
            reference="ref-1",
            user="user-1",
            org="org-1",
        )
    )
    await _pump(agent, 1)
    await asyncio.wait_for(started.wait(), timeout=2.0)

    await agent.atear_down()

    assert cancelled.is_set(), "teardown must cancel the actor's in-flight assignment"
    assert _errors(transport), (
        "the backend must be told the assignment was cancelled by the application"
    )


@pytest.mark.asyncio
async def test_teardown_is_not_hung_by_an_actor_that_ignores_cancellation(
    agent: BaseAgent,
) -> None:
    """A misbehaving actor must not be able to stall shutdown forever."""

    class _Stubborn:
        id = "stubborn"

        async def acancel(self) -> None:
            await asyncio.sleep(60)

    agent.managed_actors["stubborn"] = _Stubborn()  # type: ignore[assignment]
    agent.actor_cancel_timeout = 0.05

    await asyncio.wait_for(agent.atear_down(), timeout=2.0)


@pytest.mark.asyncio
async def test_probe_flag_on_an_assign_is_visible_to_the_agent(
    agent: BaseAgent, transport: MemoryAgentTransport
) -> None:
    """The backend marks probe invocations; the client used to drop the flag.

    ``Message`` does not forbid extra inputs, so ``probe`` was silently discarded and a
    probe was indistinguishable from a normal task -- even though locks and
    sub-assignment are unavailable under one.
    """
    assign = messages.Assign(
        task="p-1",
        interface="x",
        args={},
        implementation="impl-1",
        action="action-1",
        reference="ref-1",
        user="user-1",
        org="org-1",
        probe=True,
    )
    assert assign.probe is True

    # And it survives a round trip through the wire encoding.
    revived = messages.Assign(**json.loads(assign.model_dump_json()))
    assert revived.probe is True

    assert (
        messages.Assign(
            task="t-1",
            interface="x",
            args={},
            implementation="impl-1",
            action="action-1",
            reference="ref-1",
            user="user-1",
            org="org-1",
        ).probe
        is False
    ), "a normal assign must default to not-a-probe"


@pytest.mark.asyncio
async def test_probe_response_is_routed_to_the_caller_postman(
    agent: BaseAgent, transport: MemoryAgentTransport
) -> None:
    """A ProbeResponse answers work this agent originated, like an AssignResponse."""
    seen: List[messages.ProbeResponse] = []
    agent.caller_postman.handle_probe_response = seen.append  # type: ignore[method-assign]

    transport.feed(messages.ProbeResponse(request="req-1", probe="p-1"))
    await _pump(agent, 1)

    assert len(seen) == 1 and seen[0].probe == "p-1"


@pytest.mark.asyncio
async def test_session_init_opens_the_session_with_its_baseline_states(
    agent: BaseAgent, transport: MemoryAgentTransport
) -> None:
    """Startup must announce the session, not just snapshot into a session nobody opened.

    The backend opens the session row and records these snapshots as its baseline. The
    agent used to send a StateSnapshot here instead, which the backend accepted without
    ever learning a session had begun.
    """
    agent._current_shrunk_states["Board"] = {"count": 0}

    await agent.ainit_states(hook_return=StartupHookReturns(states={}, contexts={}))

    inits = transport.of_type(messages.SessionInit)
    assert len(inits) == 1, f"expected one SessionInit, got {transport.sent}"
    assert inits[0].session_id == agent.current_session
    assert inits[0].states == {"Board": {"count": 0}}
    assert not transport.of_type(messages.StateSnapshot), (
        "the baseline goes out as SessionInit, not as a second StateSnapshot"
    )


@pytest.mark.asyncio
async def test_a_completed_task_is_not_reported_as_still_running(
    agent: BaseAgent, transport: MemoryAgentTransport
) -> None:
    """The agent must not claim finished work is alive.

    ``_running_asyncio_tasks`` was only ever pruned on the explicit Cancel/Interrupt
    paths, so a task that simply ran to completion stayed in it forever and
    ``acheck_task`` kept answering True. That is the answer the backend gets when it
    inquires about liveness after a reconnect, so the two disagreed about what was
    running — and the map leaked an entry per assignment besides.
    """

    async def quick(x: int) -> int:
        """Finish immediately."""
        return x

    from rekuest_next.register import register

    register(
        quick,
        implementation_registry=agent.app_registry,
        structure_registry=agent.app_registry.structure_registry,
    )
    agent.collect_from_registry()

    transport.feed(
        messages.Assign(
            task="task-1",
            interface="quick",
            args={"x": 1},
            implementation="impl-1",
            action="action-1",
            reference="ref-1",
            user="user-1",
            org="org-1",
        )
    )
    await _pump(agent, 1)

    actor = agent.managed_actors["quick"]
    # Completed is emitted from inside the body, so the done callback that prunes
    # runs a tick later; wait for the task itself to retire.
    for _ in range(50):
        if transport.of_type(messages.Completed) and not actor.has_running_tasks():
            break
        await asyncio.sleep(0)
    assert transport.of_type(messages.Completed), "the task should have completed"

    assert not await actor.acheck_task("task-1"), (
        "a task that ran to completion must not report as still running"
    )
    assert not actor.has_running_tasks(), (
        "the task map must not keep growing with finished work"
    )
    assert "task-1" not in agent.managed_assignments, (
        "a terminal report must retire the assignment the agent is managing"
    )


@pytest.mark.asyncio
async def test_a_liveness_inquiry_does_not_contradict_a_replayed_report(
    agent: BaseAgent, transport: MemoryAgentTransport
) -> None:
    """Init replays retained terminal reports and *then* answers inquiries.

    Both describe the same task, so the inquiry must defer: the replayed report
    already says exactly how the task ended.
    """

    async def quick(x: int) -> int:
        """Finish immediately."""
        return x

    from rekuest_next.register import register

    register(
        quick,
        implementation_registry=agent.app_registry,
        structure_registry=agent.app_registry.structure_registry,
    )
    agent.collect_from_registry()

    transport.feed(
        messages.Assign(
            task="task-1",
            interface="quick",
            args={"x": 1},
            implementation="impl-1",
            action="action-1",
            reference="ref-1",
            user="user-1",
            org="org-1",
        )
    )
    await _pump(agent, 1)
    for _ in range(50):
        if transport.of_type(messages.Completed):
            break
        await asyncio.sleep(0)

    def _liveness_answers() -> list[messages.FromAgentMessage]:
        """Anything the agent says about task-1 other than replaying its report."""
        return [
            m
            for m in transport.sent
            if isinstance(m, (messages.Progress, messages.Critical))
            and getattr(m, "task", None) == "task-1"
        ]

    before = len(_liveness_answers())
    transport.feed(
        messages.Init(
            agent="agent-1",
            inquiries=[messages.AssignInquiry(task="task-1")],
        )
    )
    await _pump(agent, 1)

    assert len(_liveness_answers()) == before, (
        "the inquiry must defer to the replayed report, but the agent also said "
        f"{[m for m in _liveness_answers()[before:]]}"
    )


@pytest.mark.asyncio
async def test_draining_for_init_fails_when_the_stream_ends_first(
    agent: BaseAgent, transport: MemoryAgentTransport
) -> None:
    """A transport that closes before ``Init`` is not an acknowledged connection.

    ``aconnect`` must raise, not return, or the caller runs on an agent that is
    not registered anywhere (and its assignments wait forever).
    """
    agent._receiver = transport.areceive().__aiter__()
    transport.close_stream()

    with pytest.raises(AgentException):
        await asyncio.wait_for(agent._adrain_until_connected(), timeout=1)
    assert not agent._connected_event.is_set()
