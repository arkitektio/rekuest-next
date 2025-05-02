"""Base class for all structure errors."""

from rekuest_next.errors import RekuestError


class SerializationError(RekuestError):
    """Base class for all serialization errors."""

    pass


class ExpandingError(SerializationError):
    """Base class for all expanding errors."""

    pass


class ShrinkingError(SerializationError):
    """Base class for all shrinking errors."""

    pass


class PortShrinkingError(ShrinkingError):
    """Base class for all port shrinking errors."""

    pass


class PortExpandingError(ExpandingError):
    """Base class for all port expanding errors."""

    pass


class StructureShrinkingError(PortShrinkingError):
    """Raised when a structure cannot be shrunk"""

    pass


class StructureExpandingError(PortExpandingError):
    """Raised when a structure cannot be expanded"""

    pass


class StructureRegistryError(Exception):
    """Base class for all structure registry errors."""

    pass


class StructureOverwriteError(StructureRegistryError):
    """Raised when a structure is attempted to be overwritten in the registry"""

    pass


class StructureDefinitionError(StructureRegistryError):
    """Raised when a structure was never defined in the registry"""

    pass
