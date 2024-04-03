from rekuest_next.api.schema import DefinitionInput, PortKind
from typing import List, Any


def parse_collectable(definition: DefinitionInput, returns: List[Any]):
    collectables = []

    if returns is None:
        returns = []
    elif not isinstance(returns, tuple):
        returns = [returns]

    for port, v in zip(definition.returns, returns):
        # Only structures will be collected because others are passed by value
        if port.kind == PortKind.STRUCTURE:
            collectables.append((port.identifier, v))

    return collectables
