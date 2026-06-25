"""ContextLink is a link that adds a task token to the context of a graphql operation.

Its used to give some correlation information to every operation that is executed within
the context of a task.


"""

import json
from typing import AsyncIterator
from urllib.parse import quote

from rath.links.base import ContinuationLink
from rath.operation import GraphQLResult, Operation
from rath.errors import NotComposedError
from rekuest_next.actors.vars import get_current_task_helper


class ContextLink(ContinuationLink):
    """ContextLink is a link that adds an provnance token to the context.

    The provenance token is used to give some correlation information to every operation that is executed within
    the context of a task. It is signed by the rekuest server and can be used to verify the provenance of the operation.

    """

    async def aexecute(
        self, operation: Operation, retry: int = 0
    ) -> AsyncIterator[GraphQLResult]:
        """Executes and forwards an operation to the next link.

        This method will add the authentication token to the context of the operation,
        and will refresh the token if the next link raises an AuthenticationError, until
        the maximum number of refresh attempts is reached.

        Parameters
        ----------
        operation : Operation
            The operation to execute

        Yields
        ------
        GraphQLResult
            The result of the operation
        """
        if not self.next:
            raise NotComposedError("No next link set")

        try:
            helper = get_current_task_helper()

            if helper.token is not None:
                operation.context.headers["Rekuest-Task"] = helper.token

        except Exception:
            pass

        async for result in self.next.aexecute(operation):
            yield result
