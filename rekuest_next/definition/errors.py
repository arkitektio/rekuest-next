"""Errors related to definition handling"""

from rekuest_next.errors import RekuestError


class DefinitionError(RekuestError):
    """Base class for all definition errors"""

    pass


class NoDefinitionRegistryFound(RekuestError):
    """Raised when no definition registry is found"""

    pass


class NonSufficientDocumentation(DefinitionError):
    """Raised when we cannot infer sufficcient documentatoin"""
