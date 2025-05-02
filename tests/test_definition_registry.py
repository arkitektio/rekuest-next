"""Test if functions can be registered in the registry."""

from rekuest_next.definition.registry import DefinitionRegistry
from rekuest_next.register import register_func
from rekuest_next.structures.registry import StructureRegistry


def test_register_function(simple_registry: StructureRegistry) -> None:
    """Test if the function is correctly registered in the registry."""
    defi = DefinitionRegistry()

    def func() -> int:
        """This function

        This function is a test function

        """

        return 1

    register_func(func, simple_registry, defi)

    assert defi.actor_builders["func"]
