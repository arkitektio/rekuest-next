import pytest
from rekuest.definition.define import prepare_definition
from rekuest.definition.validate import auto_validate
from rekuest.structures.serialization.postman import shrink_inputs, expand_outputs
from rekuest.structures.serialization.actor import expand_inputs, shrink_outputs
from .funcs import (
    plain_basic_function,
    plain_structure_function,
    nested_structure_function,
    null_function,
    union_structure_function,
)
from .structures import SecondObject, SerializableObject
from rekuest.structures.errors import ShrinkingError, ExpandingError


@pytest.mark.shrink
@pytest.mark.asyncio
async def test_shrinking_nullable(simple_registry):
    functional_definition = prepare_definition(
        null_function, structure_registry=simple_registry
    )

    definition = auto_validate(functional_definition)

    args = await shrink_inputs(definition, (None,), {}, simple_registry)
    assert args == (None,)

    args = await shrink_inputs(definition, (1,), {}, simple_registry)
    assert args == (1,)


@pytest.mark.shrink
@pytest.mark.asyncio
async def test_shrinking_basic(simple_registry):
    functional_definition = prepare_definition(
        plain_basic_function, structure_registry=simple_registry
    )

    definition = auto_validate(functional_definition)

    args = await shrink_inputs(definition, ("hallo", "zz"), {}, simple_registry)
    assert args == ("hallo", "zz")


@pytest.mark.shrink
@pytest.mark.asyncio
async def test_rountdrip_structure(simple_registry):
    functional_definition = prepare_definition(
        plain_structure_function, structure_registry=simple_registry
    )

    definition = auto_validate(functional_definition)

    args = await shrink_inputs(
        definition,
        (SerializableObject(number=3), SerializableObject(number=3)),
        {},
        simple_registry,
    )

    for arg in args:
        assert isinstance(arg, str), "Should be a string"


@pytest.mark.asyncio
async def test_shrink_union(simple_registry):
    functional_definition = prepare_definition(
        union_structure_function, structure_registry=simple_registry
    )

    definition = auto_validate(functional_definition)

    args = await shrink_inputs(
        definition,
        (SerializableObject(number=3),),
        {},
        simple_registry,
    )

    assert args[0]["use"] == 0, "Should use the first union type"


@pytest.mark.shrink
@pytest.mark.asyncio
async def test_roundtrip(simple_registry):
    functional_definition = prepare_definition(
        plain_structure_function, structure_registry=simple_registry
    )

    definition = auto_validate(functional_definition)

    shrinked_args = await shrink_inputs(
        definition,
        (SerializableObject(number=3), SerializableObject(number=3)),
        {},
        simple_registry,
    )

    expanded_args = await expand_inputs(definition, shrinked_args, simple_registry)
    assert expanded_args["rep"].number == 3, "Should be"


@pytest.mark.shrink
@pytest.mark.asyncio
async def test_shrinking_structure_error(simple_registry):
    functional_definition = prepare_definition(
        plain_structure_function, structure_registry=simple_registry
    )

    definition = auto_validate(functional_definition)

    with pytest.raises(ShrinkingError):
        await shrink_inputs(
            definition,
            (SerializableObject(number=3), SecondObject(id=4)),
            {},
            simple_registry,
        )


@pytest.mark.shrink
@pytest.mark.asyncio
async def test_shrinking_nested_structure(simple_registry):
    functional_definition = prepare_definition(
        nested_structure_function, structure_registry=simple_registry
    )

    definition = auto_validate(functional_definition)

    args = await shrink_inputs(
        definition,
        ([SerializableObject(number=3)], {"hallo": SerializableObject(number=3)}),
        {},
        simple_registry,
    )
    assert args == (["3"], {"hallo": "3"})


@pytest.mark.expand
@pytest.mark.asyncio
async def test_expand_basic(simple_registry):
    functional_definition = prepare_definition(
        plain_basic_function, structure_registry=simple_registry
    )

    definition = auto_validate(functional_definition)

    await expand_outputs(
        definition,
        ("hallo",),
        simple_registry,
    )


@pytest.mark.expand
@pytest.mark.asyncio
async def test_expand_nested_structure_error(simple_registry):
    functional_definition = prepare_definition(
        nested_structure_function, structure_registry=simple_registry
    )

    definition = auto_validate(functional_definition)

    with pytest.raises(ExpandingError):
        await expand_outputs(
            definition,
            ([SerializableObject(number=3)], {"hallo": SerializableObject(number=3)}),
            simple_registry,
        )
