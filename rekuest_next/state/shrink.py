"""Shrink a state using a schema and a structure registry"""

from typing import Dict, Any
from rekuest_next.actors.types import Shelver
from rekuest_next.api.schema import StateSchemaInput
from rekuest_next.messages import JSONSerializable
from rekuest_next.protocols import AnyState
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.structures.serialization.actor import ashrink_return


async def ashrink_state(
    state: AnyState,  # noqa: ANN401
    schema: StateSchemaInput,
    structure_reg: StructureRegistry,  # noqa: ANN401
    shelver: Shelver,
) -> Dict[str, Any]:
    """Shrink a state  using a schema and a structure registry

    Args:
        state (Any): The state to shrink
        schema (StateSchemaInput): The schema to use (defines the ports)
        structure_reg (StructureRegistry): The structure registry to use

    Returns:
        Dict[str, Any]: The shrunk state

    """

    shrinked: Dict[str, JSONSerializable] = {}
    for port in schema.ports:
        shrinked[port.key] = await ashrink_return(
            port, getattr(state, port.key), structure_reg, shelver=shelver
        )

    return shrinked
