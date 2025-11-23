"""Exceptions raised by the Agent Transport."""

from rekuest_next.agents.errors import AgentException


class AgentTransportException(AgentException):
    """
    Base class for all exceptions raised by the Agent Transport.
    """


class BounceError(AgentTransportException):
    """
    Raised when the agent receives a bounce message.
    """


class KickError(AgentTransportException):
    """
    Raised when the agent receives a bounce message.
    """


class ProvisionListDeniedError(AgentTransportException):
    """
    Raised when the backend is not able to list the provisions.
    """


class AssignationListDeniedError(AgentTransportException):
    """
    Raised when the backend is not able to list the assignations.
    """


class CorrectableConnectionFail(AgentTransportException):
    """Raised when the connection to the agent is lost but can be restored."""

    pass


class DefiniteConnectionFail(AgentTransportException):
    """Raised when the connection to the agent is lost and cannot be restored."""

    pass


class AgentConnectionFail(AgentTransportException):
    """Base class for all exceptions raised by the Agent Transport."""

    pass


class AgentWasKicked(AgentConnectionFail):
    """Raised when the agent was kicked by the backend."""

    pass


class AgentWasBlocked(AgentConnectionFail):
    """Raised when the agent is blocked by the backend."""

    pass


class AgentIsAlreadyBusy(AgentConnectionFail):
    """Raised when the agent is already busy with another task."""

    pass
