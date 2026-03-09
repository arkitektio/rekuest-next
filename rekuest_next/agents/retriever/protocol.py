from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Protocol, runtime_checkable

from rekuest_next.messages import JSONSerializable


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
    global_revision: Optional[int]
    session_id: str


@dataclass
class PatchEvent:
    timepoint: datetime
    state_id: str
    current_rev: int
    future_rev: int
    global_current_rev: int
    global_future_rev: int
    correlation_id: str
    session_id: str
    patch: JSONSerializable


@dataclass
class TaskBoundary:
    correlation_id: str
    start_global_revision: int
    end_global_revision: int
    start_time: datetime
    end_time: datetime


@dataclass
class SessionBoundary:
    session_id: str
    start_global_revision: int
    end_global_revision: int
    start_time: datetime
    end_time: datetime


@runtime_checkable
class StateRetriever(Protocol):
    # --- READ / RETRIEVE METHODS ---

    async def ainitialize(self) -> None:
        """Should be called once to set up the sink (e.g., create tables, indexes)."""
        ...

    async def ateardown(self) -> None:
        """Cleans up resources, such as database connections."""
        ...

    async def aget_task_boundaries(
        self, correlation_id: str, state_id: Optional[str] = None
    ) -> Optional[TaskBoundary]:
        """Return the global revision boundaries and timestamps for a task."""
        ...

    async def aget_session_boundaries(
        self, session_id: str, state_id: Optional[str] = None
    ) -> Optional[SessionBoundary]:
        """Return the global revision boundaries and timestamps for a session."""
        ...

    async def aget_state_at_global_rev(
        self,
        global_revision: int,
        state_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Snapshot | List[Snapshot] | None: ...

    async def aget_state_at_local_rev(
        self,
        revision: int,
        state_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Snapshot | List[Snapshot] | None: ...

    async def aget_forward_events_after_rev(
        self,
        global_revision: int,
        state_id: Optional[str] = None,
        session_id: Optional[str] = None,
        count: int = 100,
    ) -> List[PatchEvent]:
        """Return patch events whose global revision range starts at or after `global_revision`."""
        ...

    async def aget_patch_events_between_global_revs(
        self,
        from_global_revision: int,
        to_global_revision: int,
        state_ids: Optional[List[str]] = None,
        session_id: Optional[str] = None,
    ) -> List[PatchEvent]: ...

    async def aget_snapshots_around_rev(
        self,
        revision: int,
        state_id: Optional[str] = None,
        session_id: Optional[str] = None,
        before: int = 1,
        after: int = 1,
    ) -> List[Snapshot]: ...
