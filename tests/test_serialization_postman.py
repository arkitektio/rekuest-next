"""Testing the serialization and deserialization of structures on the postman level."""

import pytest
from rekuest_next.definition.define import prepare_definition
from rekuest_next.structures.serialization.postman import ashrink_args, aexpand_returns
from rekuest_next.structures.serialization.actor import expand_inputs
from .funcs import (
    plain_basic_function,
    plain_structure_function,
    nested_structure_function,
    null_function,
    union_structure_function,
)
from .structures import SecondObject, SerializableObject
from rekuest_next.structures.errors import ShrinkingError, ExpandingError
from rekuest_next.actors.types import Shelver
from rekuest_next.structures.registry import StructureRegistry


@pytest.mark.shrink
@pytest.mark.asyncio
async def test_shrinking_nullable(
    simple_registry: StructureRegistry, mock_shelver: Shelver
) -> None:
    """Test if we can shrink a nullable input."""
    functional_definition = prepare_definition(null_function, structure_registry=simple_registry)

    args = await ashrink_args(
        functional_definition,
        (None,),
        {},
        structure_registry=simple_registry,
    )
    assert args == {"x": None}

    args = await ashrink_args(
        functional_definition,
        (1,),
        {},
        structure_registry=simple_registry,
    )
    assert args == {"x": 1}


@pytest.mark.shrink
@pytest.mark.asyncio
async def test_shrinking_basic(simple_registry: StructureRegistry, mock_shelver: Shelver) -> None:
    """Test if we can shrink a basic input."""

    functional_definition = prepare_definition(
        plain_basic_function, structure_registry=simple_registry
    )

    args = await ashrink_args(
        functional_definition,
        ("hallo", "zz"),
        {},
        structure_registry=simple_registry,
    )
    assert args == {"name": "zz", "rep": "hallo"}


@pytest.mark.shrink
@pytest.mark.asyncio
async def test_rountdrip_structure(
    simple_registry: StructureRegistry, mock_shelver: Shelver
) -> None:
    """Test if we can shrink a structure input."""
    functional_definition = prepare_definition(
        plain_structure_function, structure_registry=simple_registry
    )

    args = await ashrink_args(
        functional_definition,
        (SerializableObject(number=3), SerializableObject(number=3)),
        {},
        structure_registry=simple_registry,
    )

    for arg in args:
        assert isinstance(arg, str), "Should be a string"


@pytest.mark.asyncio
async def test_shrink_union(simple_registry: StructureRegistry, mock_shelver: Shelver) -> None:
    """Test if we can shrink a union input."""
    functional_definition = prepare_definition(
        union_structure_function, structure_registry=simple_registry
    )

    args = await ashrink_args(
        functional_definition,
        (SerializableObject(number=3),),
        {},
        structure_registry=simple_registry,
    )

    assert args["rep"]["use"] == 0, "Should use the first union type"


@pytest.mark.shrink
@pytest.mark.asyncio
async def test_roundtrip(simple_registry: StructureRegistry, mock_shelver: Shelver) -> None:
    """Test if we can shrink a structure input and expand it back."""
    functional_definition = prepare_definition(
        plain_structure_function, structure_registry=simple_registry
    )

    shrinked_args = await ashrink_args(
        functional_definition,
        (SerializableObject(number=3), SerializableObject(number=3)),
        {},
        structure_registry=simple_registry,
    )

    expanded_args = await expand_inputs(
        functional_definition,
        shrinked_args,
        structure_registry=simple_registry,
        shelver=mock_shelver,
    )
    assert expanded_args["rep"].number == 3, "Should be"


@pytest.mark.shrink
@pytest.mark.asyncio
async def test_shrinking_structure_error(
    simple_registry: StructureRegistry, mock_shelver: Shelver
) -> None:
    """Test if we can shrink a structure input with an error."""
    functional_definition = prepare_definition(
        plain_structure_function, structure_registry=simple_registry
    )

    with pytest.raises(ShrinkingError):
        await ashrink_args(
            functional_definition,
            (SerializableObject(number=3), SecondObject(id=4)),
            {},
            structure_registry=simple_registry,
        )


@pytest.mark.shrink
@pytest.mark.asyncio
async def test_shrinking_nested_structure(
    simple_registry: StructureRegistry, mock_shelver: Shelver
) -> None:
    """Test if we can shrink a nested structure input."""
    functional_definition = prepare_definition(
        nested_structure_function, structure_registry=simple_registry
    )

    args = await ashrink_args(
        functional_definition,
        ([SerializableObject(number=3)], {"hallo": SerializableObject(number=3)}),
        {},
        structure_registry=simple_registry,
    )
    assert args == {"name": {"hallo": "3"}, "rep": ["3"]}


@pytest.mark.expand
@pytest.mark.asyncio
async def test_expand_basic(simple_registry: StructureRegistry, mock_shelver: Shelver) -> None:
    """Test if we can expand a basic input."""
    functional_definition = prepare_definition(
        plain_basic_function, structure_registry=simple_registry
    )

    await aexpand_returns(
        functional_definition,
        {"return0": "hallo"},
        structure_registry=simple_registry,
    )


@pytest.mark.expand
@pytest.mark.asyncio
async def test_expand_nested_structure_error(
    simple_registry: StructureRegistry, mock_shelver: Shelver
) -> None:
    """Test if we can expand a nested structure input with an error."""
    functional_definition = prepare_definition(
        nested_structure_function, structure_registry=simple_registry
    )

    with pytest.raises(ExpandingError):
        await aexpand_returns(
            functional_definition,
            ([SerializableObject(number=3)], {"hallo": SerializableObject(number=3)}),
            structure_registry=simple_registry,
        )
