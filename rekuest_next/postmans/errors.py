"""The exceptions for the Postman module."""

from rekuest_next.errors import RekuestError


class PostmanException(RekuestError):
    """
    Base class for all exceptions raised by the Agent.
    """


class AssignException(PostmanException):
    """
    Raised when an error occurs during the assignment of a task to an agent.
    """


class RecoverableAssignException(AssignException):
    """
    Raised when an error occurs during the assignment of a task to an agent.
    """


class IncorrectReserveState(AssignException):
    """
    Raised when a task during an incorect reservation state for this contract
    """


class RootOnlyAssignError(PostmanException):
    """Raised when a non-root call is handed to a transport that only creates roots.

    A GraphQL ``assign`` creates a *root* task by definition: the backend dropped
    ``parent``/``dependency``/``method`` from ``AssignInput``, so a child task or a
    dependency method call can only be originated over the agent socket. Silently
    dropping those fields would detach a child into an orphan root, so we raise.
    """
