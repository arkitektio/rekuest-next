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
