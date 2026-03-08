from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Protocol, runtime_checkable

from kabinet.api.schema import ImplementationInput
from rekuest_next.messages import JSONSerializable
from rekuest_next.protocols import AnyState


# ==========================================
# 1. Data Models (Now using native datetime)
# ==========================================
@dataclass
class SessionInfo:
    session_id: str
    created_at: datetime


@dataclass
class Snapshot:
    timepoint: datetime
    data: JSONSerializable
    revision: int
    session_id: str


@dataclass
class PatchEvent:
    timepoint: datetime
    current_rev: int
    future_rev: int
    correlation_id: str
    session_id: str
    patch: JSONSerializable


@dataclass
class TaskBoundary:
    correlation_id: str
    start_revision: int
    end_revision: int
    start_time: datetime
    end_time: datetime


@dataclass
class SessionBoundary:
    session_id: str
    start_revision: int
    end_revision: int
    start_time: datetime
    end_time: datetime


@dataclass
class AroundWindow:
    target_revision: int
    radius_before: int
    radius_after: int
    initial_snapshot: Snapshot
    intermediate_snapshots: List[Snapshot]
    intermediate_patches: List[PatchEvent]
    end_snapshot: Snapshot


# --- Write Request Payloads ---
@dataclass
class WriteSnapshotReq:
    state_id: str
    revision: int
    global_revision: int
    state_data: JSONSerializable
    event_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: Optional[str] = None


@dataclass
class WritePatchReq:
    state_id: str
    current_rev: int
    future_rev: int
    global_current_rev: int
    global_future_rev: int
    op: str
    path: str
    value: Optional[JSONSerializable] = None
    correlation_id: str | None = None
    event_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: Optional[str] = None


@runtime_checkable
class StateSink(Protocol):
    # --- INITIALIZATION & SESSION MANAGEMENT ---
    async def ainitialize(self):
        """Should be called once to set up the sink (e.g., create tables, indexes)."""
        ...

    async def ateardown(self):
        """Cleans up resources, such as database connections."""
        ...

    async def acreate_session(
        self, states: List[AnyState], implementations: List[ImplementationInput]
    ) -> str:
        """Creates a new session and returns its ID. Should be called at the start of a new logical session.

        By default this will be called automatically on each agent startup, but can be called manually if the agent wants to manage sessions itself (e.g., create a new session for each user interaction).

        """
        ...

    # --- WRITE METHODS ---
    async def adump_snapshot(self, req: WriteSnapshotReq):
        """Will store a full snapshot of the state at a given revision. This is intended to be used for periodic checkpointing to optimize retrieval, but can also be used by agents to manually create snapshots at important milestones (e.g., end of a user interaction)."""
        ...

    async def awrite_patch(self, req: WritePatchReq):
        """Writes a patch to the store. The sink should enforce that patches are written in order (i.e., future_rev must be exactly current_rev + 1) to maintain integrity. The correlation_id can be used to group patches that belong to the same logical task or operation, which can be useful for retrieval and debugging."""
        ...

    async def is_cought_up_to(self, state_id: str, revision: int) -> bool:
        """Returns True if the sink has received patches/snapshots up to at least the given revision for the specified state_id. This can be used by agents to check if they are in sync with the latest state before performing operations that depend on up-to-date information."""
        ...
