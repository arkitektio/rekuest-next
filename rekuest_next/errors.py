"""Custom exceptions for Rekuest."""


class RekuestError(Exception):
    """Base class for all Rekuest exceptions."""

    pass


class NoRekuestRathFoundError(RekuestError):
    """Raised when no Rekuest Rathfound is found."""

    pass
