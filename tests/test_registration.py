"""Test the registration of structures in the registry."""

from rekuest_next.structures.registry import (
    StructureRegistry,
)
from rekuest_next.register import structure


def test_structure_registration() -> None:
    """Test if the structure is correctly registered in the registry."""
    registry = StructureRegistry(allow_overwrites=False)

    @structure(identifier="test", registry=registry)
    class SerializableObject:
        def __init__(self, number: int) -> None:
            super().__init__()
            self.number = number

        async def ashrink(self) -> str:
            return self.number

        @classmethod
        async def aexpand(cls, shrinked_value: str) -> "SerializableObject":
            return cls(shrinked_value)

    assert "test" in registry.identifier_structure_map, "Registration fails"


def test_structure_registration_overwrite(simple_registry: StructureRegistry) -> None:
    """Test if the structure can  be overwritten in the registry."""

    @structure(identifier="test", registry=simple_registry)
    class SerializableObject:
        def __init__(self, number: int) -> None:
            super().__init__()
            self.number = number

        @classmethod
        async def aexpand(cls, shrinked_value: str) -> "SerializableObject":
            return cls(shrinked_value)

        async def ashrink(self) -> str:
            return self.number

    @structure(identifier="test", registry=simple_registry)
    class SecondSerializableObject:
        def __init__(self, number: int) -> None:
            super().__init__()
            self.number = number

        @classmethod
        async def aexpand(cls, shrinked_value: str) -> "SerializableObject":
            return cls(shrinked_value)

        async def ashrink(self) -> str:
            return self.number
