"""Test the registration of structures in the registry."""

from rekuest_next.structures.registry import (
    StructureRegistry,
)
from rekuest_next.register import register_global
import pytest
from rekuest_next.structures.hooks.errors import HookError


def test_structure_registration() -> None:
    """Test if the structure is correctly registered in the registry."""
    registry = StructureRegistry(allow_overwrites=False)

    @register_global(identifier="test", registry=registry)
    class SerializableObject:
        def __init__(self, number: int) -> None:
            super().__init__()
            self.number = number

        async def ashrink(self) -> str:
            return self.number

        @classmethod
        async def aexpand(cls, shrinked_value: str) -> "SerializableObject":
            return cls(shrinked_value)

    assert "test" in registry._identifier_shrinker_map, "Registration fails"
    assert "test" in registry._identifier_expander_map, "Registration of expand failed"


def test_structure_registration_overwrite(simple_registry: StructureRegistry) -> None:
    """Test if the structure is correctly registered in the registry."""
    with pytest.raises(HookError):

        @register_global(identifier="test", registry=simple_registry)
        class SerializableObject:
            def __init__(self, number: int) -> None:
                super().__init__()
                self.number = number

            async def ashrink(self: int) -> str:
                return self.number

            @classmethod
            async def aexpand(cls, shrinked_value: int) -> "SerializableObject":
                return cls(shrinked_value)

    @register_global(identifier="karl", registry=simple_registry)
    class SerializableObject:
        def __init__(self, number: int) -> None:
            super().__init__()
            self.number = number

        @classmethod
        async def aexpand(cls, shrinked_value: str) -> "SerializableObject":
            return cls(shrinked_value)
