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
