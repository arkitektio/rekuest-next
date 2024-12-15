from typing import Any, Union
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.api.schema import (
    Port,
    PortKind,
    ChildPort,
)
import datetime as dt


def predicate_port(
    port: Union[Port, ChildPort],
    value: Any,
    structure_registry: StructureRegistry = None,
):
    if port.kind == PortKind.DICT:
        if not isinstance(value, dict):
            return False
        return all([predicate_port(port.child, value) for key, value in value.items()])
    if port.kind == PortKind.LIST:
        if not isinstance(value, list):
            return False
        return all([predicate_port(port.child, value) for value in value])
    if port.kind == PortKind.BOOL:
        return isinstance(value, bool)
    if port.kind == PortKind.DATE:
        return isinstance(value, dt.datetime)
    if port.kind == PortKind.INT:
        return isinstance(value, int)
    if port.kind == PortKind.FLOAT:
        return isinstance(value, float)
    if port.kind == PortKind.STRUCTURE:
        predicate = structure_registry.get_predicator_for_identifier(port.identifier)
        return predicate(value)
