"""Test the serialization logic with in memory structures"""

import pytest

from rekuest_next.actors.types import Shelver
from rekuest_next.definition.define import prepare_definition
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.structures.serialization.actor import expand_inputs, shrink_outputs

from .funcs import localized_structure_function, LocalizedStructure


@pytest.mark.expand
@pytest.mark.asyncio
async def test_local_structures(simple_registry: StructureRegistry, mock_shelver: Shelver) -> None:
    """Test if we can shrink a nullable input."""
    functional_definition = prepare_definition(
        localized_structure_function, structure_registry=simple_registry
    )

    shrinks = await shrink_outputs(
        functional_definition,
        LocalizedStructure("karl"),
        structure_registry=simple_registry,
        shelver=mock_shelver,
    )
    assert "return0" in shrinks, "Expected return_0 to be in shrinks"
    assert shrinks["return0"] in mock_shelver.shelve, (
        f"Expected {shrinks['return0']} to be in shelve"
    )
