"""Conditional detail route builders for tasks and states."""

from .states import build_state_detail_router
from .tasks import build_task_detail_router

__all__ = ["build_task_detail_router", "build_state_detail_router"]
