from rekuest_next.definition.define import prepare_definition
from rekuest_next.definition.registry import DefinitionRegistry
from rekuest_next.register import register_structure, register_func


def test_register_function(simple_registry):
    defi = DefinitionRegistry()

    def func():
        """This function

        This function is a test function

        """

        return 1

    register_func(func, simple_registry, defi)

    assert defi.actor_builders["func"]
