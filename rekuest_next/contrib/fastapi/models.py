"""Shared FastAPI response and view models for the rekuest_next FastAPI integration."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class RetrieverSessionInfoResponse(BaseModel):
    """Response containing the active session identifier."""

    current_session: str | None


class RetrieverTaskBoundaryResponse(BaseModel):
    """Response describing the revision boundaries of a task."""

    correlation_id: str
    start_revision: int
    end_revision: int
    start_time: datetime
    end_time: datetime


class RetrieverSessionBoundaryResponse(BaseModel):
    """Response describing the revision boundaries of a session."""

    session_id: str
    start_revision: int
    end_revision: int
    start_time: datetime
    end_time: datetime


class RetrieverSnapshotResponse(BaseModel):
    """Response representing a reconstructed state snapshot."""

    timepoint: datetime
    data: Any
    revision: int
    global_revision: int | None
    session_id: str


class RetrieverPatchEventResponse(BaseModel):
    """Response representing a persisted patch event."""

    timepoint: datetime
    current_rev: int
    future_rev: int
    global_current_rev: int
    global_future_rev: int
    correlation_id: str
    session_id: str
    patch: Any


class TaskView(BaseModel):
    """Current view of a managed task."""

    assignation: str
    action_key: str
    interface: str | None
    extension: str | None
    user: str | None
    app: str | None
    action: str | None
    running: bool
    actor_id: str | None


class TaskCollectionResponse(BaseModel):
    """Collection response for task overview endpoints."""

    count: int
    tasks: dict[str, TaskView]


class StateView(BaseModel):
    """Current view of a published state."""

    interface: str
    name: str
    initialized: bool
    local_revision: int
    value: Any | None = None


class StateCollectionResponse(BaseModel):
    """Collection response for state overview endpoints."""

    current_session: str | None
    current_global_revision: int | None
    count: int
    states: dict[str, StateView]


class LockView(BaseModel):
    """Current view of a managed lock."""

    interface: str
    key: str
    task_id: str | None


class LockCollectionResponse(BaseModel):
    """Collection response for lock overview endpoints."""

    count: int
    locks: dict[str, LockView]
