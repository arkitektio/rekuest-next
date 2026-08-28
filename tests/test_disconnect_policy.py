"""No-Docker checks for what a disconnect does to in-flight work.

The window these cover could not previously be observed at all. The websocket
transport retries a dropped socket transparently, so ``areceive()`` never ends and
the agent above it was never told control had been lost — an action that is only
safe while it can be cancelled just kept running. These drive that window through
:class:`tests.memory_transport.MemoryAgentTransport`, whose ``drop_link`` models
exactly it: the socket is gone, the stream is not.
"""

import asyncio
import threading
import time
from collections.abc import AsyncIterator

import pytest
from koil import check_cancelled

from rekuest_next import messages
from rekuest_next.actors.policy import (
    CancelOnDisconnect,
    DisconnectPolicy,
    OnDisconnect,
)
from rekuest_next.agents.base import BaseAgent
from rekuest_next.agents.policy import Backoff, ConnectionPolicy
from rekuest_next.app import AppRegistry
from rekuest_next.register import register

from .memory_transport import MemoryAgentTransport


@pytest.fixture()
def transport() -> MemoryAgentTransport:
    return MemoryAgentTransport()


@pytest.fixture()
def agent(transport: MemoryAgentTransport) -> BaseAgent:
    """A bare agent with its own registry, so nothing leaks between tests."""
    agent = BaseAgent(
        name="policy-test", transport=transport, app_registry=AppRegistry()
    )
    # These tests drive process() directly rather than running aconnect(), so install
    # the host by hand exactly as the connect sequence does.
    transport.set_transport_host(agent)
    return agent


async def _run_loop(agent: BaseAgent) -> AsyncIterator[None]:
    async for message in agent.transport.areceive():
        await agent.process(message)
        yield


async def _pump(agent: BaseAgent, count: int) -> None:
    """Process exactly `count` inbound messages."""
    loop = _run_loop(agent)
    for _ in range(count):
        await asyncio.wait_for(loop.__anext__(), timeout=2.0)


def _assign(task: str, interface: str) -> messages.Assign:
    return messages.Assign(
        task=task,
        interface=interface,
        args={"x": 1},
        implementation="impl-1",
        action="action-1",
        reference="ref-1",
        user="user-1",
        org="org-1",
    )


def _errors(transport: MemoryAgentTransport) -> list[str]:
    return [c.error for c in transport.of_type(messages.Critical)]


async def _settle() -> None:
    """Let the watchdog task run to completion."""
    for _ in range(20):
        await asyncio.sleep(0)


# -- the policy objects themselves -------------------------------------------------


def test_the_default_policy_keeps_work_running() -> None:
    """Opt-in, not opt-out. A long acquisition must not die on a three-second blip."""
    assert DisconnectPolicy().on_disconnect is OnDisconnect.KEEP
    assert not DisconnectPolicy().cancels_on_disconnect
    assert CancelOnDisconnect().cancels_on_disconnect


def test_backoff_is_exponential_and_capped() -> None:
    backoff = Backoff(initial=1.0, factor=2.0, max=10.0, jitter=0.0)
    assert [backoff.delay_for(n) for n in range(6)] == [1.0, 2.0, 4.0, 8.0, 10.0, 10.0]


def test_backoff_jitter_stays_within_bounds() -> None:
    """Jitter spreads a reconnecting fleet without ever producing a negative delay."""
    backoff = Backoff(initial=4.0, factor=1.0, max=4.0, jitter=0.5)
    delays = [backoff.delay_for(0) for _ in range(200)]
    assert all(2.0 <= d <= 6.0 for d in delays)
    assert len(set(delays)) > 1, "jitter should actually vary the delay"


# -- the watchdog ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_policy_stops_work_when_the_link_drops(
    agent: BaseAgent, transport: MemoryAgentTransport
) -> None:
    """The robot stops when nobody can tell it to.

    "Move until I say stop" is only safe while "I say stop" is reachable, so losing
    the control channel is itself a stop condition for this class of action.
    """
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def move_stage(x: int) -> int:
        """Run until stopped, recording that it was."""
        started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return x

    register(
        move_stage,
        policy=CancelOnDisconnect(),
        implementation_registry=agent.app_registry,
        structure_registry=agent.app_registry.structure_registry,
    )
    agent.collect_from_registry()

    transport.feed(_assign("task-1", "move_stage"))
    await _pump(agent, 1)
    await asyncio.wait_for(started.wait(), timeout=2.0)

    await transport.drop_link()
    await asyncio.wait_for(cancelled.wait(), timeout=2.0)
    await _settle()  # the report is sent after the body has finished unwinding

    assert any("control channel lost" in e for e in _errors(transport)), (
        f"the backend must be told why the work stopped, got {_errors(transport)}"
    )


@pytest.mark.asyncio
async def test_keep_policy_survives_a_drop(
    agent: BaseAgent, transport: MemoryAgentTransport
) -> None:
    """The default is untouched: a six-hour job rides out a blip."""
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def train_model(x: int) -> int:
        """Run long, and notice if something stops it."""
        started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return x

    register(
        train_model,
        implementation_registry=agent.app_registry,
        structure_registry=agent.app_registry.structure_registry,
    )
    agent.collect_from_registry()

    transport.feed(_assign("task-1", "train_model"))
    await _pump(agent, 1)
    await asyncio.wait_for(started.wait(), timeout=2.0)

    await transport.drop_link()
    await _settle()

    assert not cancelled.is_set(), "a KEEP action must survive a disconnect"
    assert "task-1" in agent.running_assignments


@pytest.mark.asyncio
async def test_only_the_declaring_action_is_stopped(
    agent: BaseAgent, transport: MemoryAgentTransport
) -> None:
    """Two actions, one agent, one drop: the policy is per-action, not per-agent."""
    started = asyncio.Event()
    other_started = asyncio.Event()
    stage_cancelled = asyncio.Event()
    scan_cancelled = asyncio.Event()

    async def move_stage(x: int) -> int:
        """Dangerous: stops when control is lost."""
        started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            stage_cancelled.set()
            raise
        return x

    async def acquire(x: int) -> int:
        """Harmless: keeps going."""
        other_started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            scan_cancelled.set()
            raise
        return x

    register(
        move_stage,
        policy=CancelOnDisconnect(),
        implementation_registry=agent.app_registry,
        structure_registry=agent.app_registry.structure_registry,
    )
    register(
        acquire,
        implementation_registry=agent.app_registry,
        structure_registry=agent.app_registry.structure_registry,
    )
    agent.collect_from_registry()

    transport.feed(_assign("task-1", "move_stage"))
    transport.feed(_assign("task-2", "acquire"))
    await _pump(agent, 2)
    await asyncio.wait_for(started.wait(), timeout=2.0)
    await asyncio.wait_for(other_started.wait(), timeout=2.0)

    await transport.drop_link()
    await asyncio.wait_for(stage_cancelled.wait(), timeout=2.0)
    await _settle()

    assert not scan_cancelled.is_set(), "the KEEP action must be left alone"


@pytest.mark.asyncio
async def test_reconnect_within_the_grace_period_spares_the_work(
    agent: BaseAgent, transport: MemoryAgentTransport
) -> None:
    """A blip shorter than the grace period is not a loss of control."""
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def scan_tile(x: int) -> int:
        """Tolerates a short blip."""
        started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return x

    register(
        scan_tile,
        policy=CancelOnDisconnect(grace=5.0),
        implementation_registry=agent.app_registry,
        structure_registry=agent.app_registry.structure_registry,
    )
    agent.collect_from_registry()

    transport.feed(_assign("task-1", "scan_tile"))
    await _pump(agent, 1)
    await asyncio.wait_for(started.wait(), timeout=2.0)

    await transport.drop_link()
    await asyncio.sleep(0)
    await transport.restore_link()
    await _settle()

    assert not cancelled.is_set(), "the link came back inside the grace period"
    assert agent._disconnect_watchdog_task is None, "the watchdog must stand down"


@pytest.mark.asyncio
async def test_a_link_that_recovers_as_the_deadline_expires_does_not_kill(
    agent: BaseAgent, transport: MemoryAgentTransport
) -> None:
    """The race the grace period creates, closed by re-checking before cancelling.

    Deadline expiry and link-up can interleave. Without a final check of
    ``transport.connected`` the work is killed over a sub-millisecond margin — or,
    worse, killed while the link is already healthy again.
    """
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def move_stage(x: int) -> int:
        """Would be stopped if the re-check were missing."""
        started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return x

    register(
        move_stage,
        policy=CancelOnDisconnect(grace=0.05),
        implementation_registry=agent.app_registry,
        structure_registry=agent.app_registry.structure_registry,
    )
    agent.collect_from_registry()

    transport.feed(_assign("task-1", "move_stage"))
    await _pump(agent, 1)
    await asyncio.wait_for(started.wait(), timeout=2.0)

    await transport.drop_link()
    # Come back up silently, without the link-up callback that would stand the
    # watchdog down. The watchdog still wakes on its deadline, so only the
    # re-check immediately before cancelling can save this work.
    await asyncio.sleep(0.01)
    transport._connected = True
    await asyncio.sleep(0.1)
    await _settle()

    assert not cancelled.is_set(), (
        "the watchdog must re-check the link immediately before cancelling"
    )


@pytest.mark.asyncio
async def test_the_kill_report_is_retained_and_resent_on_reconnect(
    agent: BaseAgent, transport: MemoryAgentTransport
) -> None:
    """A policy kill happens while the socket is down, so the report must survive it.

    Terminal reports are retained until the backend acks them and replayed on the
    next ``Init``. Without that the backend would never learn the task died.
    """
    started = asyncio.Event()

    async def move_stage(x: int) -> int:
        """Stops on disconnect."""
        started.set()
        await asyncio.sleep(60)
        return x

    register(
        move_stage,
        policy=CancelOnDisconnect(),
        implementation_registry=agent.app_registry,
        structure_registry=agent.app_registry.structure_registry,
    )
    agent.collect_from_registry()

    transport.feed(_assign("task-1", "move_stage"))
    await _pump(agent, 1)
    await asyncio.wait_for(started.wait(), timeout=2.0)

    await transport.drop_link()
    await _settle()

    assert _errors(transport), "the kill must be reported"
    before = len(transport.of_type(messages.Critical))

    transport.feed(messages.Init(agent="agent-1", inquiries=[]))
    await _pump(agent, 1)

    assert len(transport.of_type(messages.Critical)) > before, (
        "an unacked terminal report must be replayed once the link returns"
    )


@pytest.mark.asyncio
async def test_a_policy_kill_does_not_leave_the_task_looking_alive(
    agent: BaseAgent, transport: MemoryAgentTransport
) -> None:
    """After the link returns the backend asks what is still running. Answer honestly.

    ``acancel`` leaves entries in the actor's task map, so a task killed by policy
    would answer "still running" to the very inquiry that follows the reconnect.
    ``acancel_for_policy`` prunes, which is why it exists separately.
    """
    started = asyncio.Event()

    async def move_stage(x: int) -> int:
        """Stops on disconnect."""
        started.set()
        await asyncio.sleep(60)
        return x

    register(
        move_stage,
        policy=CancelOnDisconnect(),
        implementation_registry=agent.app_registry,
        structure_registry=agent.app_registry.structure_registry,
    )
    agent.collect_from_registry()

    transport.feed(_assign("task-1", "move_stage"))
    await _pump(agent, 1)
    await asyncio.wait_for(started.wait(), timeout=2.0)

    actor = agent.managed_actors["move_stage"]
    await transport.drop_link()
    await _settle()

    assert not actor.has_running_tasks(), (
        "a policy kill must prune its task bookkeeping"
    )
    assert not await actor.acheck_task("task-1"), (
        "the killed task must not answer 'still running' after the reconnect"
    )


@pytest.mark.asyncio
async def test_a_drop_with_nothing_sensitive_running_is_a_no_op(
    agent: BaseAgent, transport: MemoryAgentTransport
) -> None:
    """The common case: a blip with no dangerous work in flight costs nothing."""
    await transport.drop_link()
    await _settle()

    assert not _errors(transport)
    assert not agent._connected_event.is_set(), (
        "a drop must clear the acknowledged flag, so nothing awaits a dead link"
    )


@pytest.mark.asyncio
async def test_a_threaded_action_declaring_cancel_warns_at_registration(
    agent: BaseAgent,
) -> None:
    """We cannot force-kill a worker thread, so we must not imply that we can."""

    def move_stage_sync(x: int) -> int:
        """A sync body, which runs in a koil worker thread."""
        return x

    with pytest.warns(UserWarning, match="check_cancelled"):
        register(
            move_stage_sync,
            policy=CancelOnDisconnect(),
            implementation_registry=agent.app_registry,
            structure_registry=agent.app_registry.structure_registry,
        )


@pytest.mark.asyncio
async def test_a_polling_threaded_action_does_stop(
    agent: BaseAgent, transport: MemoryAgentTransport
) -> None:
    """The cooperative half of the threaded story, verified rather than asserted.

    A worker thread cannot be force-killed, so the honest contract is: we raise into
    it at the next ``check_cancelled()``. A body that polls really does stop.
    """
    started = threading.Event()
    stopped = threading.Event()

    def move_stage_sync(x: int) -> int:
        """A sync body that cooperates with cancellation."""
        started.set()
        try:
            for _ in range(2000):
                check_cancelled()
                time.sleep(0.005)
        except BaseException:
            stopped.set()
            raise
        return x

    with pytest.warns(UserWarning):
        register(
            move_stage_sync,
            policy=CancelOnDisconnect(),
            implementation_registry=agent.app_registry,
            structure_registry=agent.app_registry.structure_registry,
        )
    agent.collect_from_registry()

    transport.feed(_assign("task-1", "move_stage_sync"))
    await _pump(agent, 1)
    await asyncio.get_running_loop().run_in_executor(None, started.wait, 2.0)

    await transport.drop_link()
    for _ in range(200):
        if stopped.is_set():
            break
        await asyncio.sleep(0.01)

    assert stopped.is_set(), (
        "a threaded body that polls check_cancelled() must actually stop"
    )


# -- the agent-level connection policy ---------------------------------------------


def test_connection_policy_defaults_are_patient_but_bounded() -> None:
    policy = ConnectionPolicy()
    assert policy.max_retries == 5
    assert policy.reset_after > 0, (
        "a budget that is refunded by any connect at all is not a budget"
    )
    assert policy.on_exhausted == "shutdown"


def test_flap_detection_is_off_by_default() -> None:
    """``reset_after`` is the primary bound; the sliding window is opt-in."""
    assert ConnectionPolicy().flap_limit is None
