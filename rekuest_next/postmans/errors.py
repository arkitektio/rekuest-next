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
    Raised when a assignation during an incorect reservation state for this contract
    """
