from typing import AsyncIterator

from rath.links.base import ContinuationLink
from rath.operation import GraphQLResult, Operation
from rath.errors import NotComposedError
from rekuest_next.actors.vars import get_current_assignation_helper


class ContextLink(ContinuationLink):
    """ContextLink is a link that adds an assignation token to the context.
    The authentication token is retrieved by calling the token_loader function.
    If the wrapped link raises an AuthenticationError, the token_refresher function
    is called again to refresh the token.

    This link is statelss, and does not store the token. It is up to the user to
    store the token and pass it to the token_loader function.
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
            helper = get_current_assignation_helper()

            operation.context.headers["x-assignation-id"] = str(helper.assignation)

        except Exception:
            pass

        async for result in self.next.aexecute(operation):
            yield result
