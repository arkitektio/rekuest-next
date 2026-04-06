from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Protocol, runtime_checkable

from rekuest_next.messages import JSONSerializable


@dataclass
class SessionInfo:
    session_id: str
    created_at: datetime


@dataclass
class Snapshot:
    timepoint: datetime
    data: JSONSerializable
    global_revision: int
    session_id: str


@dataclass
class PatchEvent:
    timepoint: datetime
    state_id: str
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
    async def ainitialize(self) -> None: ...

    async def ateardown(self) -> None: ...

    async def aget_task_boundaries(
        self, correlation_id: str, state_id: Optional[str] = None
    ) -> Optional[TaskBoundary]: ...

    async def aget_session_boundaries(
        self, session_id: str, state_id: Optional[str] = None
    ) -> Optional[SessionBoundary]: ...

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
    ) -> List[PatchEvent]: ...
