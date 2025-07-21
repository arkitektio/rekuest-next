"""Contextual variables for assignations."""

import contextvars
from rekuest_next.actors.errors import (
    NotWithinAnAssignationError,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rekuest_next.actors.helper import AssignmentHelper


current_assignation_helper: contextvars.ContextVar["AssignmentHelper"] = contextvars.ContextVar(
    "assignment_helper"
)


def get_current_assignation_helper() -> "AssignmentHelper":
    """Get the current assignation helper."""
    try:
        return current_assignation_helper.get()
    except LookupError as e:
        raise NotWithinAnAssignationError(
            "Trying to access assignation helper outside of an assignation"
        ) from e


def is_inside_assignation() -> bool:
    """Checks if the current context is inside an assignation (e.g. was called from
    the rekuest_server)"""
    try:
        current_assignation_helper.get()
        return True
    except LookupError:
        return False
