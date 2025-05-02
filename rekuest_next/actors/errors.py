"""Exceptions for the actors module."""

from rekuest_next.errors import RekuestError


class ActorException(RekuestError):
    """An exception that is raised by an actor"""

    pass


class UnknownMessageError(ActorException):
    """An exception that is raised when an actor receives an unknown message"""

    pass


class ThreadedActorCancelled(ActorException):
    """An exception that is raised when a threaded actor is cancelled"""

    pass


class ContextError(ActorException):
    """An exception that is raised when an cannot access the context
    (probably because it is not within one)"""

    pass


class NotWithinAnAssignationError(ContextError):
    """Indicates that an actors task is not within an assignation"""

    pass


class NotWithinAProvisionError(ContextError):
    """Indicates that an actors task is not within a provision"""

    pass


class ProvisionDelegateException(ActorException):
    """An exception that is raised when trying to delageted actor"""


class DelegateException(ActorException):
    """An exception that is raised by a delageted actor"""
