from fieldz import fields, asdict
from typing import Dict, Any
from rekuest_next.api.schema import StateSchemaInput
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.structures.serialization.actor import ashrink_return


async def ashrink_state(
    state, schema: StateSchemaInput, structure_reg: StructureRegistry
) -> Dict[str, Any]:
    state_dict = asdict(state)
    shrinked = {}
    for port in schema.ports:
        shrinked[port.key] = await ashrink_return(
            port, state_dict[port.key], structure_reg
        )

    return shrinked
