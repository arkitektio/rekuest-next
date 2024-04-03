import pytest
from .structures import SerializableObject, SecondSerializableObject, GlobalObject
from rekuest.structures.registry import StructureRegistry, Scope
from rekuest.register import register_structure


async def mock_shrink():
    return


@pytest.fixture()
def simple_registry():
    registry = StructureRegistry()

    registry.register_as_structure(
        SerializableObject, identifier="x", scope=Scope.LOCAL
    )
    registry.register_as_structure(
        SecondSerializableObject, identifier="seconds", scope=Scope.LOCAL
    )

    return registry
