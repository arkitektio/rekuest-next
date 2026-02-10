"""Test the reactify function which converts a function or generator into an actor definition."""

from typing import Callable, Generator
from rekuest_next.actors.actify import reactify
from rekuest_next.api.schema import ActionKind
from rekuest_next.structures.registry import StructureRegistry
import pytest
from .funcs import nested_basic_function, nested_structure_asyncgenerator, nested_structure_function


def test_actify_function(simple_registry: StructureRegistry) -> None:
    """Test if the function is correctly buildable into an actor definition."""

    def func() -> int:
        """This function

        This function is a test function

        """

        return 1

    defi, impl_d, actor_builder = reactify(func, simple_registry)
    assert defi.kind == ActionKind.FUNCTION


def test_actify_generator(simple_registry: StructureRegistry) -> None:
    """Test if the generator is correctly buildable into an actor definition."""

    def gen() -> Generator[int, None, None]:
        """This function

        This function is a test function

        """

        yield 1

    defi, impl_d, actor_builder = reactify(gen, simple_registry)
    assert defi.kind == ActionKind.GENERATOR


@pytest.mark.parametrize(
    "func",
    [
        nested_structure_asyncgenerator,
        nested_structure_function,
        nested_basic_function,
    ],
)
def test_actify_matrix_functions(simple_registry: StructureRegistry, func: Callable) -> None:
    """Test if different function types are correctly buildable into actor definitions."""

    defi, impl_d, actor_builder = reactify(func, simple_registry)
