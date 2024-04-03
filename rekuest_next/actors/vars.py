import contextvars
from rekuest_next.actors.helper import AssignationHelper, ProvisionHelper
from rekuest_next.actors.errors import (
    NotWithinAnAssignationError,
    NotWithinAProvisionError,
)

current_assignment = contextvars.ContextVar("current_assignment")
current_assignation_helper = contextvars.ContextVar("current_assignation_helper")
current_provision_helper = contextvars.ContextVar("current_provision_helper")


def get_current_assignation_helper() -> AssignationHelper:
    try:
        return current_assignation_helper.get()
    except LookupError as e:
        raise NotWithinAnAssignationError(
            "Trying to access assignation helper outside of an assignation"
        ) from e


def get_current_provision_helper() -> ProvisionHelper:
    try:
        return current_provision_helper.get()
    except LookupError as e:
        raise NotWithinAProvisionError(
            "Trying to access provision helper outside of an provision/actor"
        ) from e
