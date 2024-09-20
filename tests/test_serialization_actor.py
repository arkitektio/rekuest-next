import pytest
from rekuest_next.definition.define import prepare_definition
from rekuest_next.definition.validate import auto_validate
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
async def test_expand_nullable(simple_registry):
    functional_definition = prepare_definition(
        null_function, structure_registry=simple_registry
    )

    definition = auto_validate(functional_definition)

    args = await expand_inputs(definition, {"x": None}, simple_registry)
    assert args == {"x": None}

    args = await expand_inputs(definition,  {"x": 1}, simple_registry)
    assert args == {"x": 1}


@pytest.mark.expand
@pytest.mark.asyncio
async def test_expand_basic(simple_registry):
    functional_definition = prepare_definition(
        plain_basic_function, structure_registry=simple_registry
    )

    definition = auto_validate(functional_definition)

    args = await expand_inputs(definition, {"name": "zz", "rep": "hallo"}, simple_registry)
    assert args == {"name": "zz", "rep": "hallo"}


@pytest.mark.expand
@pytest.mark.asyncio
async def test_expand_structure(simple_registry):
    functional_definition = prepare_definition(
        plain_structure_function, structure_registry=simple_registry
    )

    definition = auto_validate(functional_definition)

    args = await expand_inputs(
        definition,
        {"rep": 3, "name": 3},
        simple_registry,
    )
    assert args == {
        "rep": SerializableObject(number=3),
        "name": SerializableObject(number=3),
    }


@pytest.mark.expand
@pytest.mark.asyncio
async def test_expand_structure_error(simple_registry):
    functional_definition = prepare_definition(
        plain_structure_function, structure_registry=simple_registry
    )

    definition = auto_validate(functional_definition)

    with pytest.raises(ExpandingError):
        await expand_inputs(
            definition,
            {"rep": SerializableObject(number=3), "name": SecondObject(id=4)},
            simple_registry,
        )


@pytest.mark.expand
@pytest.mark.asyncio
async def test_expand_nested_structure(simple_registry):
    functional_definition = prepare_definition(
        nested_structure_function, structure_registry=simple_registry
    )

    definition = auto_validate(functional_definition)

    args = await expand_inputs(
        definition,
        {"rep": ["3"], "name": {"lala": "3"}},
        simple_registry,
    )
    assert args == {
        "rep": [SerializableObject(number=3)],
        "name": {
            "lala": SerializableObject(number=3),
        },
    }


@pytest.mark.shrink
@pytest.mark.asyncio
async def test_shrink_basic(simple_registry):
    functional_definition = prepare_definition(
        plain_basic_function, structure_registry=simple_registry
    )

    definition = auto_validate(functional_definition)

    args = await shrink_outputs(
        definition,
        ("hallo",),
        simple_registry,
    )

    assert args == {"return0": "hallo"}


@pytest.mark.shrink
@pytest.mark.asyncio
async def test_shrink_nested_structure_error(simple_registry):
    functional_definition = prepare_definition(
        nested_structure_function, structure_registry=simple_registry
    )

    definition = auto_validate(functional_definition)

    with pytest.raises(ShrinkingError):
        # Should error because first return should be string
        x = await shrink_outputs(
            definition,
            ([SerializableObject(number=3)], {"hallo": SerializableObject(number=3)}),
            simple_registry,
        )

