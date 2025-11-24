"""Custom exceptions for Rekuest."""


class RekuestError(Exception):
    """Base class for all Rekuest exceptions."""

    pass


class NoRekuestRathFoundError(RekuestError):
    """Raised when no Rekuest Rathfound is found."""

    pass


class CriticalCallError(RekuestError):
    """Raised when a critical error occurs during a remote call."""

    pass


class ErrorCallError(RekuestError):
    """Raised when an error occurs during a remote call."""

    pass
