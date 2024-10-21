import contextvars
from rekuest_next.actors.helper import AssignmentHelper
from rekuest_next.actors.errors import (
    NotWithinAnAssignationError,
)


current_assignment = contextvars.ContextVar("current_assignment")
current_assignation_helper = contextvars.ContextVar("assignment_helper")


def get_current_assignation_helper() -> AssignmentHelper:
    try:
        return current_assignation_helper.get()
    except LookupError as e:
        raise NotWithinAnAssignationError(
            "Trying to access assignation helper outside of an assignation"
        ) from e


def is_inside_assignation():
    """Checks if the current context is inside an assignation (e.g. was called from
    the rekuest_server)"""
    try:
        current_assignment.get()
        return True
    except LookupError:
        return False
