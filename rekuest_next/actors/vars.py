"""Contextual variables for tasks."""

import contextvars
from rekuest_next.actors.errors import (
    NotWithinATaskError,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rekuest_next.actors.helper import AssignmentHelper


current_task_helper: contextvars.ContextVar["AssignmentHelper"] = (
    contextvars.ContextVar("assignment_helper")
)


def get_current_task_helper() -> "AssignmentHelper":
    """Get the current task helper."""
    try:
        return current_task_helper.get()
    except LookupError as e:
        raise NotWithinATaskError(
            "Trying to access task helper outside of a task"
        ) from e


def get_current_task_id_or_none() -> str | None:
    """Get the current task id."""
    try:
        helper = current_task_helper.get()
        return helper.assignment.task
    except LookupError:
        return None
