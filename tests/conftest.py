import pytest
from .structures import SerializableObject, SecondSerializableObject
from rekuest_next.structures.registry import StructureRegistry, PortScope


async def mock_shrink() -> None:
    return


class MockShelver:
    def __init__(self):
        self.shelve = {}

    async def aput_on_shelve(self, value: object) -> str:
        """Put a value on the shelve and return the key. This is used to store
        values on the shelve."""
        key = str(id(value))
        self.shelve[key] = value
        return key

    async def aget_from_shelve(self, key: str) -> object:
        """Get a value from the shelve. This is used to get values from the
        shelve."""
        return self.shelve[key]


@pytest.fixture()
def simple_registry() -> StructureRegistry:
    """Fixture for a simple registry"""
    registry = StructureRegistry()

    return registry


@pytest.fixture()
def mock_shelver() -> MockShelver:
    """Fixture for a mock shelver"""
    return MockShelver()
