"""The default structure registry for Rekuest Next."""

from rekuest_next.structures.registry import StructureRegistry
from .utils import id_shrink


def get_default_structure_registry() -> StructureRegistry:
    """Return the default structure registry (the app registry's).

    Returns:
        StructureRegistry: The structure registry of the global app registry.
    """
    from rekuest_next.app import get_default_app_registry

    return get_default_app_registry().structure_registry


__all__ = [
    "get_default_structure_registry",
    "id_shrink",
]
