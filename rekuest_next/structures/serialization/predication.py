"""Predication module for Rekuest Next."""

from typing import Any
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.api.schema import (
    ChildPortNestedChildren,
    PortInput,
    PortKind,
)
import datetime as dt

from rekuest_next.structures.serialization.protocols import SerializablePort


def predicate_port_input(
    port: PortInput,
    value: Any,  # noqa: ANN401
    structure_registry: StructureRegistry,
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

        if not port.children:
            raise ValueError(f"Port {port.identifier} has no children")

        return all(
            [
                predicate_port_input(port.children[0], value, structure_registry)
                for key, value in value.items()  # type: ignore
            ]
        )
    if port.kind == PortKind.LIST:
        if not isinstance(value, list):
            return False

        if not port.children:
            raise ValueError(f"Port {port.identifier} has no children")

        return all(
            [
                predicate_port_input(port.children[0], value, structure_registry)
                for value in value  # type: ignore
            ]
        )
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
        if not port.identifier:
            raise ValueError(f"Port {port} has no identifier")

        fstruc = structure_registry.get_fullfilled_structure(port.identifier)
        return fstruc.predicate(value)
    if port.kind == PortKind.MODEL:
        if not port.identifier:
            raise ValueError(f"Port {port} has no identifier")
        fstruc = structure_registry.get_fullfilled_model(port.identifier)
        return fstruc.predicate(value)
    if port.kind == PortKind.MEMORY_STRUCTURE:
        if not port.identifier:
            raise ValueError(f"Port {port} has no identifier")
        fstruc = structure_registry.get_fullfilled_memory_structure(port.identifier)
        return fstruc.predicate(value)
    if port.kind == PortKind.ENUM:
        if not port.identifier:
            raise ValueError(f"Port {port} has no identifier")
        fstruc = structure_registry.get_fullfilled_enum(port.identifier)
        return fstruc.predicate(value)

    raise ValueError(f"Unknown port kind: {port.kind} to predicate")


def predicate_serializable_port(
    port: SerializablePort,
    value: Any,  # noqa: ANN401
    structure_registry: StructureRegistry,
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

        if isinstance(port, ChildPortNestedChildren):
            raise ValueError(f"Maximum recursion depth exceeded for port {port.identifier}")

        if not port.children:
            raise ValueError(f"Port {port.identifier} has no children")

        if len(port.children) != 1:
            raise ValueError(f"Port {port.identifier} has no children")

        child_port = port.children[0]
        return all(
            [
                predicate_serializable_port(child_port, value, structure_registry)
                for key, value in value.items()  # type: ignore
            ]
        )
    if port.kind == PortKind.LIST:
        if not isinstance(value, dict):
            return False

        if isinstance(port, ChildPortNestedChildren):
            raise ValueError(f"Maximum recursion depth exceeded for port {port.identifier}")

        if not port.children:
            raise ValueError(f"Port {port.identifier} has no children")

        if len(port.children) != 1:
            raise ValueError(f"Port {port.identifier} has no children")

        child_port = port.children[0]
        return all(
            [
                predicate_serializable_port(child_port, value, structure_registry)
                for value in value  # type: ignore
            ]
        )
    if port.kind == PortKind.MODEL:
        if isinstance(port, ChildPortNestedChildren):
            raise ValueError(f"Maximum recursion depth exceeded for port {port.identifier}")

        if not port.children:
            raise ValueError(f"Port {port.identifier} has no children")

        all_ports_match = True

        for child_port in port.children:
            child_value = getattr(value, child_port.key)

            if not predicate_serializable_port(
                child_port, getattr(value, child_value), structure_registry
            ):
                all_ports_match = False
                break

        return all_ports_match

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
        if not port.identifier:
            raise ValueError(f"Port {port} has no identifier")
        fstruc = structure_registry.get_fullfilled_structure(port.identifier)
        return fstruc.predicate(value)
    if port.kind == PortKind.MEMORY_STRUCTURE:
        if not port.identifier:
            raise ValueError(f"Port {port} has no identifier")

        fstruc = structure_registry.get_fullfilled_memory_structure(port.identifier)
        return fstruc.predicate(value)
    if port.kind == PortKind.ENUM:
        if not port.identifier:
            raise ValueError(f"Port {port} has no identifier")
        fstruc = structure_registry.get_fullfilled_enum(port.identifier)
        return fstruc.predicate(value)

    raise ValueError(f"Unknown port kind: {port.kind} to predicate")
