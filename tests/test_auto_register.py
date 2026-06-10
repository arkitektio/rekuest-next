"""Tests for the structure registry's auto-registration dispatch."""

from enum import Enum

from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.structures.types import (
    FullFilledEnum,
    FullFilledMemoryStructure,
    FullFilledStructure,
)


class ColorEnum(Enum):
    """A color choice"""

    RED = "red"
    GREEN = "green"


class GlobalThing:
    """A global structure implementing the identifier protocol."""

    def __init__(self, id: str) -> None:
        """Initialize the object with an id."""
        self.id = id

    @classmethod
    def get_identifier(cls) -> str:
        """Get the identifier of the object."""
        return "mock/globalthing"

    async def ashrink(self) -> str:
        """Shrink the object to its id."""
        return self.id

    @classmethod
    async def aexpand(cls, value: str) -> "GlobalThing":
        """Expand the object from its id."""
        return cls(id=value)

    @classmethod
    def convert_default(cls, value: "GlobalThing") -> str:
        """Convert a default value to its id."""
        return f"converted-{value.id}"


class PlainThing:
    """A plain class that should land in the local shelve."""

    pass


def test_auto_register_enum() -> None:
    """Enums are auto-registered as fullfilled enums with choices."""
    registry = StructureRegistry()
    fullfilled = registry.get_fullfilled_type_for_cls(ColorEnum)
    assert isinstance(fullfilled, FullFilledEnum)
    assert [c.label for c in fullfilled.choices] == ["RED", "GREEN"]
    assert fullfilled.convert_default(ColorEnum.RED) == "RED"


def test_auto_register_global_structure() -> None:
    """Classes with the identifier protocol become global structures."""
    registry = StructureRegistry()
    fullfilled = registry.get_fullfilled_type_for_cls(GlobalThing)
    assert isinstance(fullfilled, FullFilledStructure)
    assert fullfilled.identifier == "mock/globalthing"


def test_auto_register_respects_convert_default() -> None:
    """A class's own convert_default classmethod must be used, not the
    identity converter."""
    registry = StructureRegistry()
    fullfilled = registry.get_fullfilled_type_for_cls(GlobalThing)
    assert isinstance(fullfilled, FullFilledStructure)
    assert fullfilled.convert_default is not None
    assert fullfilled.convert_default(GlobalThing(id="x")) == "converted-x"


def test_auto_register_memory_structure_fallback() -> None:
    """Plain classes fall back to memory structures with a derived identifier."""
    registry = StructureRegistry()
    fullfilled = registry.get_fullfilled_type_for_cls(PlainThing)
    assert isinstance(fullfilled, FullFilledMemoryStructure)
    assert fullfilled.identifier == f"{PlainThing.__module__.lower()}.plainthing"
