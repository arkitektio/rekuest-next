"""Test that typing.Literal annotations are autoconverted to enum ports."""

from typing import Literal

import pytest

from rekuest_next.actors.types import Shelver
from rekuest_next.api.schema import PortKind
from rekuest_next.definition.define import prepare_definition
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.structures.serialization.actor import expand_inputs, shrink_outputs


def literal_arg_function(x: Literal["a", "b", "c"]) -> str:
    """A function with a literal argument."""
    return x


def literal_default_function(x: Literal["a", "b", "c"] = "b") -> str:
    """A function with a literal argument that has a default."""
    return x


def literal_int_function(x: Literal[1, 2, 3]) -> str:
    """A function with an int literal argument."""
    return str(x)


def literal_return_function(x: int) -> Literal["a", "b", "c"]:
    """A function returning a literal."""
    return "a"


def test_literal_arg_becomes_enum_port(simple_registry: StructureRegistry) -> None:
    """A bare Literal arg should produce an ENUM port with the right choices."""
    definition = prepare_definition(
        literal_arg_function, structure_registry=simple_registry
    )
    port = definition.args[0]
    assert port.kind == PortKind.ENUM
    assert [choice.value for choice in port.choices] == ["a", "b", "c"]


def test_literal_default_becomes_enum_port(simple_registry: StructureRegistry) -> None:
    """A Literal with a string default must not be mistaken for a STRING port."""
    definition = prepare_definition(
        literal_default_function, structure_registry=simple_registry
    )
    port = definition.args[0]
    assert port.kind == PortKind.ENUM
    assert port.default == "b"


def test_literal_int_becomes_enum_port(simple_registry: StructureRegistry) -> None:
    """Int literals are autoconverted too (and not treated as plain INT)."""
    definition = prepare_definition(
        literal_int_function, structure_registry=simple_registry
    )
    port = definition.args[0]
    assert port.kind == PortKind.ENUM
    assert [choice.value for choice in port.choices] == ["1", "2", "3"]


def test_literal_return_becomes_enum_port(simple_registry: StructureRegistry) -> None:
    """Literals in the return annotation are autoconverted too."""
    definition = prepare_definition(
        literal_return_function, structure_registry=simple_registry
    )
    port = definition.returns[0]
    assert port.kind == PortKind.ENUM
    assert [choice.value for choice in port.choices] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_literal_roundtrip(
    simple_registry: StructureRegistry, mock_shelver: Shelver
) -> None:
    """Expand a wire value into a literal arg, then shrink it back."""
    definition = prepare_definition(
        literal_return_function, structure_registry=simple_registry
    )

    args = await expand_inputs(
        definition,
        {"x": 5},
        structure_registry=simple_registry,
        shelver=mock_shelver,
    )
    assert args["x"] == 5

    shrunk = await shrink_outputs(
        definition,
        literal_return_function(5),
        structure_registry=simple_registry,
        shelver=mock_shelver,
    )
    assert shrunk["return0"] == "a"


@pytest.mark.asyncio
async def test_literal_arg_expand_roundtrip(
    simple_registry: StructureRegistry, mock_shelver: Shelver
) -> None:
    """A wire choice for a literal arg expands to a value equal to that choice."""
    definition = prepare_definition(
        literal_arg_function, structure_registry=simple_registry
    )

    args = await expand_inputs(
        definition,
        {"x": "c"},
        structure_registry=simple_registry,
        shelver=mock_shelver,
    )
    # str-based enum member compares and stringifies as the bare literal value.
    assert args["x"] == "c"
    assert str(args["x"]) == "c"


def test_same_literal_shares_identifier(simple_registry: StructureRegistry) -> None:
    """The same Literal used twice resolves to the same enum identifier."""
    definition_a = prepare_definition(
        literal_arg_function, structure_registry=simple_registry
    )
    definition_b = prepare_definition(
        literal_default_function, structure_registry=simple_registry
    )
    assert definition_a.args[0].identifier == definition_b.args[0].identifier
