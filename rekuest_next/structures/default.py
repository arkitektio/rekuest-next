"""The default structure registry for Rekuest Next."""

from rekuest_next.structures.registry import StructureRegistry
from .utils import id_shrink

DEFAULT_STRUCTURE_REGISTRY = None


def get_default_structure_registry() -> StructureRegistry:
    """Get the default structure registry.

    If no global structure registry has been set, this will return the
    structure registry from the global app registry.

    Returns:
        StructureRegistry: The default structure registry.
    """
    global DEFAULT_STRUCTURE_REGISTRY
    if not DEFAULT_STRUCTURE_REGISTRY:
        from rekuest_next.app import get_default_app_registry

        return get_default_app_registry().structure_registry

    return DEFAULT_STRUCTURE_REGISTRY


def set_default_structure_registry(registry: StructureRegistry) -> None:
    """Set a standalone default structure registry.

    This bypasses the app registry and sets a specific structure registry
    as the global default.

    Args:
        registry: The StructureRegistry to use as default.
    """
    global DEFAULT_STRUCTURE_REGISTRY
    DEFAULT_STRUCTURE_REGISTRY = registry


__all__ = [
    "get_default_structure_registry",
    "set_default_structure_registry",
    "id_shrink",
]
