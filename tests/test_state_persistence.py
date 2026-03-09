from dataclasses import dataclass

import asyncio
import pytest

from rekuest_next import messages
from rekuest_next.agents.base import BaseAgent
from rekuest_next.agents.retriever.memory_retriever import MemoryRetriever
from rekuest_next.agents.sink.memory_sink import MemorySink, MemoryStore
from rekuest_next.agents.sink.protocol import WritePatchReq, WriteSnapshotReq
from rekuest_next.agents.transport.test_transport import TestAgentTransport
from rekuest_next.state.decorator import state
from rekuest_next.state.publish import Patch


@state(name="QueuedCounterState")
@dataclass
class QueuedCounterState:
    value: int = 0


class DummyStateWorker:
    def __init__(self) -> None:
        self.patches: list[Patch] = []

    def put_patch(self, patch: Patch) -> None:
        self.patches.append(patch)


class DummyAgent(BaseAgent[None]):
    async def apublish_envelope(self, interface: str, envelope: messages.Envelope) -> None:
        return None

    async def apublish_states(self, state_implementation):
        return None

    async def aregister_definitions(self, instance_id: str, app_context):
        return None

    def get_structure_registry_for_interface(self, interface: str):
        return self.states[interface].__rekuest_state_config__.structure_registry


@pytest.mark.asyncio
async def test_agent_queues_patches_and_periodically_snapshots() -> None:
    state_instance = QueuedCounterState()
    interface = state_instance.__rekuest_state_config__.state_name
    sink = MemorySink()
    worker = DummyStateWorker()

    agent = DummyAgent(
        transport=TestAgentTransport(),
        sink=sink,
        retriever=MemoryRetriever(),
        snapshot_interval=2,
    )
    agent.states[interface] = state_instance
    agent.current_session = "session-1"
    agent._interface_stateschema_input_map[interface] = (
        state_instance.__rekuest_state_config__.state_schema
    )
    agent._current_shrunk_states[interface] = {"value": 0}
    agent._state_revisions[interface] = 0
    agent._state_workers[interface] = worker  # type: ignore[assignment]
    agent._event_queue = asyncio.Queue()
    agent._patch_processor_task = asyncio.create_task(agent.apatch_event_loop())

    agent.publish_patch(
        interface,
        Patch(op="replace", path="/value", value=1, correlation_id="corr-1"),
    )
    agent.publish_patch(
        interface,
        Patch(op="replace", path="/value", value=2, correlation_id="corr-1"),
    )

    await asyncio.wait_for(agent._event_queue.join(), timeout=1)

    assert [patch.value for patch in sink.store.patches] == [1, 2]
    assert agent._current_shrunk_states[interface]["value"] == 2
    assert agent._state_revisions[interface] == 2
    assert agent.global_revision == 2
    assert len(sink.store.snapshots) == 1
    assert sink.store.snapshots[0].revision == 2
    assert sink.store.snapshots[0].state_data["value"] == 2
    assert len(worker.patches) == 2

    agent._patch_processor_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await agent._patch_processor_task


@pytest.mark.asyncio
async def test_memory_retriever_reads_async_sink_history() -> None:
    store = MemoryStore()
    sink = MemorySink(memory=store)
    retriever = MemoryRetriever(store=store)
    session_id = await sink.acreate_session(states=[], implementations=[])

    await sink.adump_snapshot(
        WriteSnapshotReq(
            state_id="QueuedCounterState",
            revision=0,
            global_revision=0,
            state_data={"value": 0},
            session_id=session_id,
        )
    )
    await sink.awrite_patch(
        WritePatchReq(
            state_id="QueuedCounterState",
            current_rev=0,
            future_rev=1,
            global_current_rev=0,
            global_future_rev=1,
            op="replace",
            path="/value",
            value=1,
            correlation_id="corr-2",
            session_id=session_id,
        )
    )
    await sink.adump_snapshot(
        WriteSnapshotReq(
            state_id="SecondaryState",
            revision=0,
            global_revision=1,
            state_data={"value": 10},
            session_id=session_id,
        )
    )
    await sink.awrite_patch(
        WritePatchReq(
            state_id="SecondaryState",
            current_rev=0,
            future_rev=1,
            global_current_rev=1,
            global_future_rev=2,
            op="replace",
            path="/value",
            value=11,
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
    assert state_at_local.revision == 1
    assert state_at_local.global_revision == 1
    assert state_at_local.data["value"] == 1

    state_at_global = await retriever.aget_state_at_global_rev(
        state_id="QueuedCounterState",
        global_revision=1,
        session_id=session_id,
    )
    assert state_at_global is not None
    assert state_at_global.revision == 1
    assert state_at_global.global_revision == 1

    forward_events = await retriever.aget_forward_events_after_rev(
        state_id="QueuedCounterState",
        global_revision=0,
        session_id=session_id,
        count=10,
    )
    assert len(forward_events) == 1
    assert forward_events[0].future_rev == 1
    assert forward_events[0].global_future_rev == 1

    snapshots = await retriever.aget_snapshots_around_rev(
        state_id="QueuedCounterState",
        revision=1,
        session_id=session_id,
        before=1,
        after=1,
    )
    assert len(snapshots) == 1
    assert snapshots[0].revision == 0

    all_state_at_local = await retriever.aget_state_at_local_rev(
        revision=1,
        session_id=session_id,
    )
    assert all_state_at_local is not None
    assert len(all_state_at_local) == 2
    assert sorted(snapshot.data["value"] for snapshot in all_state_at_local) == [1, 11]

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
