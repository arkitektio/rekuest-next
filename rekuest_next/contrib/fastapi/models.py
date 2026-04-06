"""Shared FastAPI response and view models for the rekuest_next FastAPI integration."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RetrieverSessionInfoResponse(BaseModel):
    """Response containing the active session identifier."""

    current_session: str | None


class RetrieverTaskBoundaryResponse(BaseModel):
    """Response describing the global revision boundaries of a task."""

    correlation_id: str
    start_global_revision: int
    end_global_revision: int
    start_time: datetime
    end_time: datetime


class RetrieverSessionBoundaryResponse(BaseModel):
    """Response describing the global revision boundaries of a session."""

    session_id: str
    start_global_revision: int
    end_global_revision: int
    start_time: datetime
    end_time: datetime


class RetrieverSnapshotResponse(BaseModel):
    """Response representing a reconstructed state snapshot."""

    timepoint: datetime
    data: Any
    global_revision: int
    session_id: str


class RetrieverPatchEventResponse(BaseModel):
    """Response representing a persisted patch event."""

    timepoint: datetime
    state_id: str
    global_current_rev: int
    global_future_rev: int
    correlation_id: str
    session_id: str
    patch: Any


class StateSegmentsResponse(BaseModel):
    """Response representing persisted patches within a global revision range."""

    from_global_revision: int
    to_global_revision: int
    patches: list[RetrieverPatchEventResponse]


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
    value: Any | None = None


class StateCollectionResponse(BaseModel):
    """Collection response for state overview endpoints."""

    current_session: str | None
    current_global_revision: int | None
    count: int
    states: dict[str, StateView]
    recent_patches: list[RetrieverPatchEventResponse] = Field(default_factory=lambda: [])


class LockView(BaseModel):
    """Current view of a managed lock."""

    interface: str
    key: str
    task_id: str | None


class LockCollectionResponse(BaseModel):
    """Collection response for lock overview endpoints."""

    count: int
    locks: dict[str, LockView]


class WebSocketSubscriptionInit(BaseModel):
    """Init payload sent by websocket clients after connecting.

    All filter lists are optional. When omitted, the websocket receives all
    messages of that category. State batching can be customized per state key
    through `state_update_intervals`. Use `"*"` for a default interval.
    """

    type: str | None = None
    action_keys: list[str] | None = None
    state_keys: list[str] | None = None
    lock_keys: list[str] | None = None
    state_update_intervals: dict[str, float] | None = None
