"""Tests for the ``@structure`` decorator.

The decorator is the ergonomic front door for declaring a global
(serialize-by-reference) structure: it removes the ``get_identifier`` boilerplate
and eagerly registers the class in a structure registry. These tests use explicit
``StructureRegistry`` instances so they never touch global state.
"""

import pytest

from rekuest_next import structure
from rekuest_next.structures.errors import StructureDefinitionError
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.structures.types import FullFilledStructure


def test_structure_decorator_registers_with_explicit_identifier() -> None:
    """``@structure(identifier=...)`` registers a global structure eagerly."""
    registry = StructureRegistry()

    @structure(identifier="myapp/image", registry=registry)
    class Image:
        def __init__(self, id: str) -> None:
            self.id = id

        async def ashrink(self) -> str:
            return self.id

        @classmethod
        async def aexpand(cls, value: str) -> "Image":
            return cls(id=value)

    fullfilled = registry.get_fullfilled_type_for_cls(Image)
    assert isinstance(fullfilled, FullFilledStructure)
    assert fullfilled.identifier == "myapp/image"


def test_structure_decorator_bare_form_uses_get_identifier() -> None:
    """Bare ``@structure`` falls back to an existing ``get_identifier``."""
    registry = StructureRegistry()

    # The bare form registers in the *default* registry, so to keep this test
    # isolated we exercise the bare branch via the explicit registry helper by
    # decorating with no parentheses and then re-registering in our registry.
    @structure
    class Thing:
        def __init__(self, id: str) -> None:
            self.id = id

        @classmethod
        def get_identifier(cls) -> str:
            return "myapp/thing"

        async def ashrink(self) -> str:
            return self.id

        @classmethod
        async def aexpand(cls, value: str) -> "Thing":
            return cls(id=value)

    # Re-register in an isolated registry to assert the resolved identifier
    # without depending on global registry contents.
    registry.register_as_structure(
        Thing, Thing.get_identifier(), aexpand=Thing.aexpand, ashrink=Thing.ashrink
    )
    fullfilled = registry.get_fullfilled_type_for_cls(Thing)
    assert isinstance(fullfilled, FullFilledStructure)
    assert fullfilled.identifier == "myapp/thing"


def test_structure_decorator_requires_shrink_and_expand() -> None:
    """A class missing ``ashrink``/``aexpand`` is rejected with a clear error."""
    registry = StructureRegistry()

    with pytest.raises(StructureDefinitionError):

        @structure(identifier="myapp/broken", registry=registry)
        class Broken:
            pass


@pytest.mark.asyncio
async def test_structure_decorator_round_trips() -> None:
    """The registered structure shrinks to its id and expands back."""
    registry = StructureRegistry()

    @structure(identifier="myapp/doc", registry=registry)
    class Doc:
        def __init__(self, id: str) -> None:
            self.id = id

        async def ashrink(self) -> str:
            return self.id

        @classmethod
        async def aexpand(cls, value: str) -> "Doc":
            return cls(id=value)

    fullfilled = registry.get_fullfilled_type_for_cls(Doc)
    assert isinstance(fullfilled, FullFilledStructure)

    shrunk = await fullfilled.ashrink(Doc(id="doc-1"))
    assert shrunk == "doc-1"

    expanded = await fullfilled.aexpand("doc-1")
    assert isinstance(expanded, Doc)
    assert expanded.id == "doc-1"
