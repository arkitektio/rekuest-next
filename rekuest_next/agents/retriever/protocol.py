import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Protocol, runtime_checkable

import aiosqlite

from rekuest_next.messages import JSONSerializable
from xest_no import dt_to_epoch_ms


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


@runtime_checkable
class StateRetriever(Protocol):
    # --- READ / RETRIEVE METHODS ---

    async def ainitialize(self):
        """Should be called once to set up the sink (e.g., create tables, indexes)."""
        ...

    async def ateardown(self):
        """Cleans up resources, such as database connections."""
        ...

    async def aget_task_boundaries(
        self, correlation_id: str, state_id: Optional[str] = None
    ) -> Optional[TaskBoundary]:
        """Given a state_id and a correlation_id, returns the start and end revisions and timestamps for that task. This allows agents to query the history of a specific operation or task, which can be useful for debugging, auditing, or reconstructing the sequence of events that led to a particular state."""
        ...

    async def aget_session_boundaries(
        self, session_id: str, state_id: Optional[str] = None
    ) -> Optional[SessionBoundary]: ...

    async def aget_around_window(
        self,
        state_id: str,
        target_revision: int,
        session_id: Optional[str] = None,
        radius_before: int = 100,
        radius_after: int = 100,
    ) -> Optional[AroundWindow]: ...
