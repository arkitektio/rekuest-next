class AgentException(Exception):
    """
    Base class for all exceptions raised by the Agent.
    """


class ProvisionException(AgentException):
    """
    Base class for all exceptions raised by the Agent.
    """


class ExtensionError(AgentException):
    """
    Base class for all exceptions raised by an Extension of the Agent.
    """
