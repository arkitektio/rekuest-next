from dataclasses import dataclass
from rekuest_next.messages import Assignation, Provision
from rekuest_next.actors.helper import AssignationHelper, ProvisionHelper
from rekuest_next.actors.vars import (
    current_assignation_helper,
    current_provision_helper,
    current_assignment,
)
from rekuest_next.actors.transport.types import ActorTransport, AssignTransport
from rekuest_next.actors.types import Assignment, Passport
from pydantic import BaseModel


class AssignationContext(BaseModel):
    passport: Passport
    assignment: Assignment
    transport: AssignTransport
    _helper = None

    def __enter__(self):
        self._helper = AssignationHelper(
            assignment=self.assignment, transport=self.transport, passport=self.passport
        )

        current_assignment.set(self.assignment)
        current_assignation_helper.set(self._helper)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        current_assignation_helper.set(None)
        current_assignment.set(None)
        self._helper = None

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)

    class Config:
        arbitrary_types_allowed = True
        underscore_attrs_are_private = True


class ProvisionContext(BaseModel):
    provision: Provision
    transport: ActorTransport
    _helper = None

    def __enter__(self):
        self._helper = ProvisionHelper(
            provision=self.provision, transport=self.transport
        )

        current_provision_helper.set(self._helper)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        current_provision_helper.set(None)
        self._helper = None

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)

    class Config:
        arbitrary_types_allowed = True
        underscore_attrs_are_private = True
