from dataclasses import dataclass

import asyncio
import janus
import pytest
from datetime import datetime, timezone
from pydantic import Field, PrivateAttr

from rekuest_next import messages
from rekuest_next.agents.base import BaseAgent
from rekuest_next.contrib.fastapi.retriever.memory_retriever import MemoryRetriever
from rekuest_next.contrib.fastapi.sink.memory_sink import MemorySink, MemoryStore
from rekuest_next.contrib.fastapi.sink.protocol import StateSink
from rekuest_next.agents.transport.test_transport import TestAgentTransport
from rekuest_next.state.decorator import state
from rekuest_next.state.publish import Patch


@state(name="QueuedCounterState")
@dataclass
class QueuedCounterState:
    value: int = 0


class DummyAgent(BaseAgent[None]):
    sink: StateSink = Field(default_factory=lambda: MemorySink())
    sink_catch_up_timeout: float | None = Field(default=5.0)
    sink_catch_up_poll_interval: float = Field(default=0.05)
    _published_envelopes: list[messages.StatePatchEvent] = PrivateAttr(default_factory=list)

    async def apublish_patch(self, envelope: messages.StatePatchEvent) -> None:
        self._published_envelopes.append(envelope)
        await self.sink.awrite_patch(envelope)

    async def _acreate_session(self) -> str:
        return await self.sink.acreate_session(states=[], implementations=[])

    async def _await_persistence_caught_up(self) -> None:
        poll_interval = max(self.sink_catch_up_poll_interval, 0.0)

        async def _wait() -> None:
            while not await self.sink.is_cought_up_to(self.global_revision):
                await asyncio.sleep(poll_interval)

        if self.sink_catch_up_timeout is None:
            await _wait()
            return
        try:
            await asyncio.wait_for(_wait(), timeout=self.sink_catch_up_timeout)
        except asyncio.TimeoutError:
            pass

    async def atear_down(self) -> None:
        await super().atear_down()
        await self._await_persistence_caught_up()
        await self.sink.ateardown()

    async def apublish_states(self, state_implementation):
        return None

    async def aregister_definitions(self, instance_id: str, app_context):
        return None

    def get_structure_registry_for_interface(self, interface: str):
        return self.states[interface].__rekuest_state_config__.structure_registry


class DelayedCatchupSink(MemorySink):
    def __init__(self, delay: float) -> None:
        super().__init__()
        self.delay = delay
        self._caught_up_revision: int = 0
        self._tasks: list[asyncio.Task[None]] = []

    async def awrite_patch(self, patch: messages.StatePatchEvent):
        async def _persist_later() -> None:
            await asyncio.sleep(self.delay)
            self.store.patches.append(patch)
            self._caught_up_revision = patch.global_rev

        self._tasks.append(asyncio.create_task(_persist_later()))

    async def is_cought_up_to(self, revision: int) -> bool:
        return self._caught_up_revision >= revision

    async def ateardown(self):
        if self._tasks:
            await asyncio.gather(*self._tasks)
        await super().ateardown()


@pytest.mark.asyncio
async def test_agent_queues_patches_and_publishes_envelopes() -> None:
    state_instance = QueuedCounterState()
    interface = state_instance.__rekuest_state_config__.state_name
    value_port = state_instance.__rekuest_state_config__.state_schema.ports[0]
    sink = MemorySink()

    agent = DummyAgent(
        transport=TestAgentTransport(),
        sink=sink,
        snapshot_interval=2,
    )
    agent.states[interface] = state_instance
    agent.current_session = "session-1"
    agent._interface_stateschema_input_map[interface] = (
        state_instance.__rekuest_state_config__.state_schema
    )
    agent._current_shrunk_states[interface] = {"value": 0}
    agent._event_queue = janus.Queue()
    agent._patch_processor_task = asyncio.create_task(agent.apatch_event_loop())

    agent.publish_patch(
        interface,
        Patch(op="replace", path="/value", value=1, port=value_port, correlation_id="corr-1"),
    )
    agent.publish_patch(
        interface,
        Patch(op="replace", path="/value", value=2, port=value_port, correlation_id="corr-1"),
    )

    await asyncio.wait_for(agent._event_queue.async_q.join(), timeout=1)

    assert [patch.value for patch in sink.store.patches] == [1, 2]
    assert agent._current_shrunk_states[interface]["value"] == 2
    assert agent.global_revision == 2
    assert sink.store.snapshots == []
    assert len(agent._published_envelopes) == 2
    assert [envelope.value for envelope in agent._published_envelopes] == [1, 2]

    await agent.atear_down()


@pytest.mark.asyncio
async def test_memory_retriever_reads_async_sink_history() -> None:
    store = MemoryStore()
    sink = MemorySink(memory=store)
    retriever = MemoryRetriever(store=store)
    session_id = await sink.acreate_session(states=[], implementations=[])

    await sink.adump_snapshot(
        messages.StateSnapshotEvent(
            session_id=session_id,
            global_rev=0,
            snapshots={"QueuedCounterState": {"value": 0}},
        )
    )
    await sink.awrite_patch(
        messages.StatePatchEvent(
            state_name="QueuedCounterState",
            global_rev=1,
            ts=datetime.now(timezone.utc).timestamp(),
            op="replace",
            path="/value",
            value=1,
            old_value=None,
            correlation_id="corr-2",
            session_id=session_id,
        )
    )
    await sink.adump_snapshot(
        messages.StateSnapshotEvent(
            session_id=session_id,
            global_rev=1,
            snapshots={"SecondaryState": {"value": 10}},
        )
    )
    await sink.awrite_patch(
        messages.StatePatchEvent(
            state_name="SecondaryState",
            global_rev=2,
            ts=datetime.now(timezone.utc).timestamp(),
            op="replace",
            path="/value",
            value=11,
            old_value=None,
            correlation_id="corr-3",
            session_id=session_id,
        )
    )

    boundaries = await retriever.aget_task_boundaries(
        correlation_id="corr-2",
        state_id="QueuedCounterState",
    )
    assert boundaries is not None
    assert boundaries.start_global_revision == 0
    assert boundaries.end_global_revision == 1

    session_boundaries = await retriever.aget_session_boundaries(
        session_id=session_id,
        state_id="QueuedCounterState",
    )
    assert session_boundaries is not None
    assert session_boundaries.end_global_revision == 1

    state_at_local = await retriever.aget_state_at_local_rev(
        state_id="QueuedCounterState",
        revision=1,
        session_id=session_id,
    )
    assert state_at_local is not None
    assert state_at_local.global_revision == 1
    assert state_at_local.data["value"] == 1

    state_at_global = await retriever.aget_state_at_global_rev(
        state_id="QueuedCounterState",
        global_revision=1,
        session_id=session_id,
    )
    assert state_at_global is not None
    assert state_at_global.global_revision == 1

    forward_events = await retriever.aget_forward_events_after_rev(
        state_id="QueuedCounterState",
        global_revision=0,
        session_id=session_id,
        count=10,
    )
    assert len(forward_events) == 1
    assert forward_events[0].global_future_rev == 1

    snapshots = await retriever.aget_snapshots_around_rev(
        state_id="QueuedCounterState",
        revision=1,
        session_id=session_id,
        before=1,
        after=1,
    )
    assert len(snapshots) == 1
    assert snapshots[0].global_revision == 0

    all_state_at_local = await retriever.aget_state_at_local_rev(
        revision=1,
        session_id=session_id,
    )
    assert all_state_at_local is not None
    assert len(all_state_at_local) == 2
    assert sorted(snapshot.data["value"] for snapshot in all_state_at_local) == [1, 10]

    all_state_at_global = await retriever.aget_state_at_global_rev(
        global_revision=2,
        session_id=session_id,
    )
    assert all_state_at_global is not None
    assert len(all_state_at_global) == 2
    assert sorted(snapshot.data["value"] for snapshot in all_state_at_global) == [1, 11]

    all_forward_events = await retriever.aget_forward_events_after_rev(
        global_revision=0,
        session_id=session_id,
        count=10,
    )
    assert len(all_forward_events) == 2
    assert sorted(event.global_future_rev for event in all_forward_events) == [1, 2]

    all_snapshots = await retriever.aget_snapshots_around_rev(
        revision=1,
        session_id=session_id,
        before=1,
        after=1,
    )
    assert len(all_snapshots) == 2
    assert sorted(snapshot.data["value"] for snapshot in all_snapshots) == [0, 10]


@pytest.mark.asyncio
async def test_agent_teardown_waits_for_sink_catch_up() -> None:
    state_instance = QueuedCounterState()
    interface = state_instance.__rekuest_state_config__.state_name
    value_port = state_instance.__rekuest_state_config__.state_schema.ports[0]
    sink = DelayedCatchupSink(delay=0.05)

    agent = DummyAgent(
        transport=TestAgentTransport(),
        sink=sink,
        sink_catch_up_timeout=1.0,
        sink_catch_up_poll_interval=0.01,
    )
    agent.states[interface] = state_instance
    agent.current_session = "session-1"
    agent._interface_stateschema_input_map[interface] = (
        state_instance.__rekuest_state_config__.state_schema
    )
    agent._current_shrunk_states[interface] = {"value": 0}
    agent._event_queue = janus.Queue()
    agent._patch_processor_task = asyncio.create_task(agent.apatch_event_loop())

    agent.publish_patch(
        interface,
        Patch(op="replace", path="/value", value=1, port=value_port, correlation_id="corr-1"),
    )

    await agent.atear_down()

    assert [patch.value for patch in sink.store.patches] == [1]
    assert await sink.is_cought_up_to(1)
