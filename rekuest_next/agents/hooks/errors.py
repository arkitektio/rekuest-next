"""Errors for hooks"""

from rekuest_next.agents.errors import AgentException


class HookError(AgentException):
    """
    Base class for all exceptions raised by a hook
    """


class StartupHookError(HookError):
    """
    Raised when a startup hook fails
    """


class BackgroundHookError(HookError):
    """
    Raised when a background hook fails
    """
