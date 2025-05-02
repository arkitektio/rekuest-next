"""Hook errors module."""

from rekuest_next.structures.errors import StructureRegistryError


class HookError(StructureRegistryError):
    """Base class for all hook errors."""

    pass
