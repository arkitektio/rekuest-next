"""Predication module for Rekuest Next."""

from typing import Any, Union
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.api.schema import (
    Port,
    PortInput,
    PortKind,
)
import datetime as dt


def predicate_port(
    port: Union[Port, PortInput],
    value: Any,  # noqa: ANN401
    structure_registry: StructureRegistry = None,
) -> bool:
    """Check if the value is of the correct type for the structure.

    Args:
        port (Union[Port, PortInput]): The port to check.
        value (Any): The value to check.
        structure_registry (StructureRegistry, optional): The structure registry. Defaults to None.
    Returns:
        bool: True if the value is of the correct type for the structure, False otherwise.
    """
    if port.kind == PortKind.DICT:
        if not isinstance(value, dict):
            return False
        return all([predicate_port(port.children[0], value) for key, value in value.items()])
    if port.kind == PortKind.LIST:
        if not isinstance(value, list):
            return False
        return all([predicate_port(port.children[0], value) for value in value])
    if port.kind == PortKind.DATE:
        return isinstance(value, dt.datetime)
    if port.kind == PortKind.INT:
        return isinstance(value, int)
    if port.kind == PortKind.FLOAT:
        return isinstance(value, float)
    if port.kind == PortKind.BOOL:
        return isinstance(value, bool)
    if port.kind == PortKind.STRING:
        return isinstance(value, str)
    if port.kind == PortKind.STRUCTURE:
        fstruc = structure_registry.get_fullfilled_structure(port.identifier)
        return fstruc.predicate(value)
    if port.kind == PortKind.MODEL:
        fstruc = structure_registry.get_fullfilled_model(port.identifier)
        return fstruc.predicate(value)
    if port.kind == PortKind.MEMORY_STRUCTURE:
        fstruc = structure_registry.get_fullfilled_memory_structure(port.identifier)
        return fstruc.predicate(value)
    if port.kind == PortKind.ENUM:
        fstruc = structure_registry.get_fullfilled_enum(port.identifier)
        return fstruc.predicate(value)

    raise ValueError(f"Unknown port kind: {port.kind} to predicate")
