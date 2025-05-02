import pytest
from rekuest_next.definition.define import prepare_definition
from rekuest_next.definition.validate import auto_validate
from rekuest_next.structures.serialization.actor import expand_inputs
from rekuest_next.structures.registry import StructureRegistry
from enum import Enum
from functools import partial
from rekuest_next.actors.types import Shelver


def alert_function_a(x: int) -> str:
    """Alert function A"""
    return "a"


def alert_function_b(x: int) -> str:
    """Alert function B"""
    return "b"


def alert_function_c(x: int) -> str:
    """Alert function C"""
    return "c"


class FunctionEnum(Enum):
    """Enum for the functions"""

    A = partial(alert_function_a)
    B = partial(alert_function_b)
    C = partial(alert_function_c)


def enum_function(x: FunctionEnum) -> str:
    """Enum function

    Does the enum thing

    """
    return x(x)


def enum_function_default(x: FunctionEnum = FunctionEnum.A) -> str:
    """Enum function

    Does the enum thing

    """
    return x(x)


@pytest.mark.expand
@pytest.mark.asyncio
async def test_expand_enums_partial_functions(
    simple_registry: StructureRegistry, mock_shelver: Shelver
) -> None:
    """Test if we can expand enums that have partial functions"""
    functional_definition = prepare_definition(enum_function, structure_registry=simple_registry)

    definition = auto_validate(functional_definition)

    args = await expand_inputs(
        definition, {"x": "C"}, structure_registry=simple_registry, shelver=mock_shelver
    )
    func = args["x"]  #
    assert func.value(1) == "c", "Enum function should expand to the correct function"


# @pytest.mark.expand
@pytest.mark.asyncio
async def test_expand_enums_default(
    simple_registry: StructureRegistry, mock_shelver: Shelver
) -> None:
    """Test the default value of the enum function"""
    functional_definition = prepare_definition(
        enum_function_default, structure_registry=simple_registry
    )

    definition = auto_validate(functional_definition)

    args = await expand_inputs(
        definition, {"x": None}, structure_registry=simple_registry, shelver=mock_shelver
    )
    func = args["x"]  #
    assert func.value(1) == "a", "Enum function should expand to the correct function"
