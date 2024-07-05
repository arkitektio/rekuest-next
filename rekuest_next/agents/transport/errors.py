from rekuest_next.agents.errors import AgentException


class AgentTransportException(AgentException):
    """
    Base class for all exceptions raised by the Agent Transport.
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
    pass


class DefiniteConnectionFail(AgentTransportException):
    pass


class AgentConnectionFail(AgentTransportException):
    pass


class AgentWasKicked(AgentConnectionFail):
    pass


class AgentWasBlocked(AgentConnectionFail):
    pass


class AgentIsAlreadyBusy(AgentConnectionFail):
    pass
