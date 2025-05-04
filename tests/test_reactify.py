"""Test the reactify function which converts a function or generator into an actor definition."""

from typing import Generator
from rekuest_next.actors.actify import reactify
from rekuest_next.api.schema import ActionKind
from rekuest_next.structures.registry import StructureRegistry


def test_actify_function(simple_registry: StructureRegistry) -> None:
    """Test if the function is correctly buildable into an actor definition."""

    def func() -> int:
        """This function

        This function is a test function

        """

        return 1

    defi, actor_builder = reactify(func, simple_registry)
    assert defi.kind == ActionKind.FUNCTION


def test_actify_generator(simple_registry: StructureRegistry) -> None:
    """Test if the generator is correctly buildable into an actor definition."""

    def gen() -> Generator[int, None, None]:
        """This function

        This function is a test function

        """

        yield 1

    defi, actor_builder = reactify(gen, simple_registry)
    assert defi.kind == ActionKind.GENERATOR
