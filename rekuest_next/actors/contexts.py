from rekuest_next.messages import Assign
from rekuest_next.actors.helper import AssignmentHelper
from rekuest_next.actors.vars import (
    current_assignation_helper,
    current_assignment,
)
from rekuest_next.actors.transport.types import AssignTransport
from rekuest_next.actors.types import Passport
from pydantic import BaseModel, ConfigDict


class AssignmentContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    passport: Passport
    assignment: Assign
    transport: AssignTransport
    _helper = None

    def __enter__(self):
        self._helper = AssignmentHelper(
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
