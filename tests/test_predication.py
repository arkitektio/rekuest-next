"""Tests for union-branch predication over ports."""

from typing import List, Union

import pytest

from rekuest_next.api.schema import ArgPortInput, PortKind
from rekuest_next.definition.define import prepare_definition
from rekuest_next.structures.model import model
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.structures.serialization.postman import ashrink_args
from rekuest_next.structures.serialization.predication import predicate_port


def test_list_port_predicates_lists_not_dicts() -> None:
    """A LIST port matches a list of matching items and rejects a dict."""
    port = ArgPortInput(
        key="xs",
        kind=PortKind.LIST,
        nullable=False,
        children=(ArgPortInput(key="item", kind=PortKind.INT, nullable=False),),
    )
    registry = StructureRegistry()
    assert predicate_port(port, [1, 2, 3], registry) is True
    assert predicate_port(port, {"a": 1}, registry) is False
    assert predicate_port(port, ["a"], registry) is False


@model
class Point:
    """A registered model."""

    x: int
    y: int


def point_or_int(value: Union[Point, int]) -> int:
    """Accepts a Point or an int."""
    return 1


def list_or_str(value: Union[List[int], str]) -> int:
    """Accepts a list of ints or a str."""
    return 1


@pytest.mark.asyncio
async def test_union_shrink_selects_model_branch() -> None:
    """A model value passed to a ``Model | int`` union picks the model branch."""
    registry = StructureRegistry()
    definition = prepare_definition(point_or_int, structure_registry=registry)

    shrunk = await ashrink_args(
        definition, (Point(x=1, y=2),), {}, structure_registry=registry
    )
    assert shrunk["value"]["__use"] == 0
    assert shrunk["value"]["__value"]["x"] == 1

    shrunk = await ashrink_args(definition, (7,), {}, structure_registry=registry)
    assert shrunk["value"] == {"__use": 1, "__value": 7}


@pytest.mark.asyncio
async def test_union_shrink_selects_list_branch() -> None:
    """A list value passed to a ``List[int] | str`` union picks the list branch."""
    registry = StructureRegistry()
    definition = prepare_definition(list_or_str, structure_registry=registry)

    shrunk = await ashrink_args(definition, ([1, 2],), {}, structure_registry=registry)
    assert shrunk["value"] == {"__use": 0, "__value": [1, 2]}

    shrunk = await ashrink_args(definition, ("s",), {}, structure_registry=registry)
    assert shrunk["value"] == {"__use": 1, "__value": "s"}
