from fieldz import asdict
from typing import Dict, Any
from rekuest_next.api.schema import StateSchemaInput
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.structures.serialization.actor import ashrink_return


async def ashrink_state(
    state: Any, schema: StateSchemaInput, structure_reg: StructureRegistry
) -> Dict[str, Any]:
    """ Shrink a state  using a schema and a structure registry

    Args:
        state (Any): The state to shrink
        schema (StateSchemaInput): The schema to use (defines the ports)
        structure_reg (StructureRegistry): The structure registry to use

    Returns:
        Dict[str, Any]: The shrunk state
    
    """



    state_dict = asdict(state)
    shrinked = {}
    for port in schema.ports:
        shrinked[port.key] = await ashrink_return(
            port, state_dict[port.key], structure_reg
        )

    return shrinked
