"""SetAssignationLink"""

from rath.links.base import ContinuationLink
from rath.operation import GraphQLResult, Operation
from typing import AsyncIterator
from rekuest_next.actors.vars import (
    current_assignation_helper,
)


class SetAssignationLink(ContinuationLink):
    """SetAssignationLink"""

    header_name: str = "x-assignation-id"

    async def aexecute(self, operation: Operation) -> AsyncIterator[GraphQLResult]:  # noqa: ANN003
        """Execute the link"""
        if not self.next:
            raise ValueError("Next link is not set")

        try:
            assignment = current_assignation_helper.get()
            operation.context.headers[self.header_name] = assignment.assignation
        except LookupError:
            pass

        async for result in self.next.aexecute(operation):
            yield result
