"""The default structure registry for Rekuest Next."""

from rekuest_next.structures.registry import StructureRegistry

DEFAULT_STRUCTURE_REGISTRY = None


async def id_shrink(
    value: object,
) -> object:
    """Identity shrink function.

    This function does not change the value and is used as a default shrink function for structures.

    Args:
        value (object): The value to be shrunk.
        structure_registry (StructureRegistry): The structure registry.

    Returns:
        object: The shrunk value.
    """
    if hasattr(value, "id"):
        return value.id
    else:
        raise ValueError(f"Value {value} does not have an id attribute. Cannot shrink.")


def get_default_structure_registry() -> StructureRegistry:
    """Get the default structure registry.

    Gets the default structure registry. If it does not exist, it will create one and import the structures from the local modules and installed packages.


    """
    global DEFAULT_STRUCTURE_REGISTRY
    if not DEFAULT_STRUCTURE_REGISTRY:
        DEFAULT_STRUCTURE_REGISTRY = StructureRegistry()

    return DEFAULT_STRUCTURE_REGISTRY
