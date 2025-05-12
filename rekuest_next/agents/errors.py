"""This module contains the exceptions used in the Agent."""


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


class StateRequirementsNotMet(AgentException):
    """
    Raised when the state requirements are not met
    """


class ContextRequirementsNotMet(AgentException):
    """
    Raised when the context requirements are not met
    """
