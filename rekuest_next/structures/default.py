"""The default structure registry for Rekuest Next."""

from rekuest_next.structures.registry import StructureRegistry
from .utils import id_shrink

DEFAULT_STRUCTURE_REGISTRY = None


def get_default_structure_registry() -> StructureRegistry:
    """Get the default structure registry.

    Gets the default structure registry. If it does not exist, it will create one and import the structures from the local modules and installed packages.


    """
    global DEFAULT_STRUCTURE_REGISTRY
    if not DEFAULT_STRUCTURE_REGISTRY:
        DEFAULT_STRUCTURE_REGISTRY = StructureRegistry()  # type: ignore

    return DEFAULT_STRUCTURE_REGISTRY


__all__ = [
    "get_default_structure_registry",
    "id_shrink",
]
