"""Grouped FastAPI route helpers for task, state, and lock endpoints."""

from .locks import add_lock_route, add_lock_routes, add_lock_websocket_route
from .states import (
    GlobalStateItemResponse,
    GlobalStatesResponse,
    add_state_route,
    add_state_routes,
    add_state_websocket_route,
)
from .tasks import add_task_websocket_route

__all__ = [
    "GlobalStateItemResponse",
    "GlobalStatesResponse",
    "add_lock_route",
    "add_lock_routes",
    "add_lock_websocket_route",
    "add_state_route",
    "add_state_routes",
    "add_state_websocket_route",
    "add_task_websocket_route",
]
