"""Test the serialization logic on the actor side"""

import pytest
from rekuest_next.actors.types import Shelver
from rekuest_next.definition.define import prepare_definition
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.structures.serialization.actor import shrink_outputs, expand_inputs
from .funcs import (
    plain_basic_function,
    plain_structure_function,
    nested_structure_function,
    null_function,
)
from .structures import SecondObject, SerializableObject
from rekuest_next.structures.errors import ShrinkingError, ExpandingError
from rekuest_next.api.schema import (
    DefinitionInput,
    PortInput,
    PortKind,
    ActionKind,
)
from typing import Any


@pytest.mark.expand
@pytest.mark.asyncio
async def test_expand_nullable(simple_registry: StructureRegistry, mock_shelver: Shelver) -> None:
    """Test if we can shrink a nullable input."""
    functional_definition = prepare_definition(null_function, structure_registry=simple_registry)

    args = await expand_inputs(
        functional_definition, {"x": None}, structure_registry=simple_registry, shelver=mock_shelver
    )
    assert args == {"x": None}

    args = await expand_inputs(
        functional_definition, {"x": 1}, structure_registry=simple_registry, shelver=mock_shelver
    )
    assert args == {"x": 1}


@pytest.mark.expand
@pytest.mark.asyncio
async def test_expand_basic(simple_registry: StructureRegistry, mock_shelver: Shelver) -> None:
    """Test if we can shrink a basic input."""
    functional_definition = prepare_definition(
        plain_basic_function, structure_registry=simple_registry
    )

    args = await expand_inputs(
        functional_definition,
        {"name": "zz", "rep": "hallo"},
        structure_registry=simple_registry,
        shelver=mock_shelver,
    )
    assert args == {"name": "zz", "rep": "hallo"}


@pytest.mark.expand
@pytest.mark.asyncio
async def test_expand_structure(simple_registry: StructureRegistry, mock_shelver: Shelver) -> None:
    """Test if we can shrink a structure input."""
    functional_definition = prepare_definition(
        plain_structure_function, structure_registry=simple_registry
    )

    args = await expand_inputs(
        functional_definition,
        {"rep": 3, "name": 3},
        structure_registry=simple_registry,
        shelver=mock_shelver,
    )
    assert args == {
        "rep": SerializableObject(number=3),
        "name": SerializableObject(number=3),
    }


@pytest.mark.expand
@pytest.mark.asyncio
async def test_expand_structure_error(
    simple_registry: StructureRegistry, mock_shelver: Shelver
) -> None:
    """Test if we can expand a structure input with an error."""
    functional_definition = prepare_definition(
        plain_structure_function, structure_registry=simple_registry
    )

    with pytest.raises(ExpandingError):
        await expand_inputs(
            functional_definition,
            {"rep": SerializableObject(number=3), "name": SecondObject(id=4)},
            structure_registry=simple_registry,
            shelver=mock_shelver,
        )


@pytest.mark.expand
@pytest.mark.asyncio
async def test_expand_nested_structure(
    simple_registry: StructureRegistry, mock_shelver: Shelver
) -> None:
    """Test if we can expand a nested structure input."""
    functional_definition = prepare_definition(
        nested_structure_function, structure_registry=simple_registry
    )

    args = await expand_inputs(
        functional_definition,
        {"rep": ["3"], "name": {"lala": "3"}},
        structure_registry=simple_registry,
        shelver=mock_shelver,
    )
    assert args == {
        "rep": [SerializableObject(number=3)],
        "name": {
            "lala": SerializableObject(number=3),
        },
    }


@pytest.mark.shrink
@pytest.mark.asyncio
async def test_shrink_basic(simple_registry: StructureRegistry, mock_shelver: Shelver) -> None:
    """Test if we can shrink a basic input."""
    functional_definition = prepare_definition(
        plain_basic_function, structure_registry=simple_registry
    )

    args = await shrink_outputs(
        functional_definition,
        ("hallo",),
        structure_registry=simple_registry,
        shelver=mock_shelver,
    )

    assert args == {"return0": "hallo"}


@pytest.mark.shrink
@pytest.mark.asyncio
async def test_shrink_nested_structure_error(
    simple_registry: StructureRegistry, mock_shelver: Shelver
) -> None:
    """Test if we can shrink a structure input with an error."""
    functional_definition = prepare_definition(
        nested_structure_function, structure_registry=simple_registry
    )

    with pytest.raises(ShrinkingError):
        # Should error because first return should be string
        await shrink_outputs(
            functional_definition,
            ([SerializableObject(number=3)], {"hallo": SerializableObject(number=3)}),
            structure_registry=simple_registry,
            shelver=mock_shelver,
        )


def simple_func(x: int, y: str = "default") -> str:
    """A simple function for testing."""
    return f"{y}-{x}"


@pytest.mark.asyncio
async def test_expand_custom_definition(
    simple_registry: StructureRegistry, mock_shelver: Shelver
) -> None:
    """Test expanding inputs with a manually created definition."""

    # Create a custom definition
    definition = DefinitionInput(
        name="custom_func",
        description="A custom function",
        args=(
            PortInput(key="arg1", kind=PortKind.STRING, nullable=False),
            PortInput(key="arg2", kind=PortKind.INT, nullable=True),
            PortInput(key="arg3", kind=PortKind.BOOL, nullable=False),
        ),
        returns=(),
        kind=ActionKind.FUNCTION,
        collections=(),
        interfaces=(),
        portGroups=(),
        isDev=False,
        stateful=False,
        isTestFor=(),
    )

    # Test valid inputs
    inputs = {"arg1": "hello", "arg2": 123, "arg3": True}
    expanded = await expand_inputs(
        definition, inputs, structure_registry=simple_registry, shelver=mock_shelver
    )

    assert expanded["arg1"] == "hello"
    assert expanded["arg2"] == 123
    assert expanded["arg3"] is True

    # Test nullable input
    inputs_nullable = {"arg1": "world", "arg2": None, "arg3": False}
    expanded_nullable = await expand_inputs(
        definition, inputs_nullable, structure_registry=simple_registry, shelver=mock_shelver
    )

    assert expanded_nullable["arg1"] == "world"
    assert expanded_nullable["arg2"] is None
    assert expanded_nullable["arg3"] is False


@pytest.mark.asyncio
async def test_shrink_custom_definition(
    simple_registry: StructureRegistry, mock_shelver: Shelver
) -> None:
    """Test shrinking outputs with a manually created definition."""

    # Create a custom definition
    definition = DefinitionInput(
        name="custom_func_out",
        description="A custom function output",
        args=(),
        returns=(
            PortInput(key="ret1", kind=PortKind.STRING, nullable=False),
            PortInput(key="ret2", kind=PortKind.FLOAT, nullable=False),
        ),
        kind=ActionKind.FUNCTION,
        collections=(),
        interfaces=(),
        portGroups=(),
        isDev=False,
        stateful=False,
        isTestFor=(),
    )

    # Test valid outputs
    # shrink_outputs expects returns as a list/tuple matching the definition returns
    outputs = ("result", 3.14)
    shrunk = await shrink_outputs(
        definition, outputs, structure_registry=simple_registry, shelver=mock_shelver
    )

    assert shrunk["ret1"] == "result"
    assert shrunk["ret2"] == 3.14


@pytest.mark.asyncio
async def test_expand_custom_list_dict(
    simple_registry: StructureRegistry, mock_shelver: Shelver
) -> None:
    """Test expanding list and dict inputs with a manually created definition."""

    definition = DefinitionInput(
        name="custom_complex",
        description="Complex inputs",
        args=(
            PortInput(
                key="list_arg",
                kind=PortKind.LIST,
                children=(PortInput(key="item", kind=PortKind.INT, nullable=False),),
                nullable=False,
            ),
            PortInput(
                key="dict_arg",
                kind=PortKind.DICT,
                children=(PortInput(key="val", kind=PortKind.STRING, nullable=False),),
                nullable=False,
            ),
        ),
        returns=(),
        kind=ActionKind.FUNCTION,
        collections=(),
        interfaces=(),
        portGroups=(),
        isDev=False,
        stateful=False,
        isTestFor=(),
    )

    inputs = {"list_arg": [1, 2, 3], "dict_arg": {"a": "x", "b": "y"}}

    expanded = await expand_inputs(
        definition, inputs, structure_registry=simple_registry, shelver=mock_shelver
    )

    assert expanded["list_arg"] == [1, 2, 3]
    assert expanded["dict_arg"] == {"a": "x", "b": "y"}


@pytest.mark.asyncio
async def test_expand_function_definition(
    simple_registry: StructureRegistry, mock_shelver: Shelver
) -> None:
    """Test expanding inputs using a definition generated from a function."""

    definition = prepare_definition(simple_func, structure_registry=simple_registry)

    # Check if definition is correct
    assert definition.name == "Simple Func"
    assert len(definition.args) == 2
    assert definition.args[0].key == "x"
    assert definition.args[0].kind == PortKind.INT
    assert definition.args[1].key == "y"
    assert definition.args[1].kind == PortKind.STRING
    assert (
        definition.args[1].nullable is True
    )  # It has a default value, so it is nullable in the sense of optional input?

    inputs: dict[str, Any] = {"x": 10}
    expanded = await expand_inputs(
        definition, inputs, structure_registry=simple_registry, shelver=mock_shelver
    )

    assert expanded["x"] == 10
    assert expanded["y"] == "default"  # Should use default value

    inputs_explicit: dict[str, Any] = {"x": 20, "y": "explicit"}
    expanded_explicit = await expand_inputs(
        definition, inputs_explicit, structure_registry=simple_registry, shelver=mock_shelver
    )

    assert expanded_explicit["x"] == 20
    assert expanded_explicit["y"] == "explicit"
