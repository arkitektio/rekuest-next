import pytest
from .structures import SerializableObject, SecondSerializableObject
from rekuest_next.structures.registry import StructureRegistry, PortScope


async def mock_shrink():
    return


@pytest.fixture()
def simple_registry():
    registry = StructureRegistry()

    registry.register_as_structure(
        SerializableObject, identifier="x", scope=PortScope.LOCAL
    )
    registry.register_as_structure(
        SecondSerializableObject, identifier="seconds", scope=PortScope.LOCAL
    )

    return registry
