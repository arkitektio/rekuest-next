"""SetAssignationLink"""

from rath.links.base import ContinuationLink
from rath.operation import GraphQLResult, Operation
from typing import AsyncIterator
from rekuest_next.actors.vars import (
    current_assignment,
)


class SetAssignationLink(ContinuationLink):
    """SetAssignationLink"""

    header_name: str = "x-assignation-id"

    async def aconnect(self) -> None:
        """Connect the link"""
        pass

    async def aexecute(self, operation: Operation, **kwargs) -> AsyncIterator[GraphQLResult]:  # noqa: ANN003
        """Execute the link"""
        try:
            assignment = current_assignment.get()
            operation.context.headers[self.header_name] = assignment.assignation
        except LookupError:
            pass

        async for result in self.next.aexecute(operation, **kwargs):
            yield result
