"""Predication: decide whether a Python value fits a port.

Used to pick the matching branch of a ``UNION`` port before shrinking.
"""

import datetime as dt
from typing import Any

from rekuest_next.api.schema import PortKind
from rekuest_next.structures.quantities import matches_dimension
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.structures.serialization.protocols import SerializablePort


def _single_child(port: SerializablePort) -> SerializablePort:
    if not port.children or len(port.children) != 1:
        raise ValueError(f"Port {port.identifier} must have exactly one child")
    return port.children[0]


def _require_identifier(port: SerializablePort) -> str:
    if not port.identifier:
        raise ValueError(f"Port {port} has no identifier")
    return port.identifier


def predicate_port(
    port: SerializablePort,
    value: Any,  # noqa: ANN401
    structure_registry: StructureRegistry,
) -> bool:
    """Check whether ``value`` is of the type described by ``port``.

    Container kinds recurse into their children; registered kinds
    (structure / model / memory structure / enum) defer to the predicate the
    registry recorded for the identifier.

    Raises:
        ValueError: If the port is malformed (missing identifier / children) or
            of an unknown kind.
    """
    kind = port.kind
    if kind == PortKind.DICT:
        if not isinstance(value, dict):
            return False
        child = _single_child(port)
        return all(
            predicate_port(child, item, structure_registry)
            for item in value.values()  # type: ignore[union-attr]
        )
    if kind == PortKind.LIST:
        if not isinstance(value, list):
            return False
        child = _single_child(port)
        return all(
            predicate_port(child, item, structure_registry)
            for item in value  # type: ignore[union-attr]
        )
    if kind == PortKind.DATE:
        return isinstance(value, dt.datetime)
    if kind == PortKind.INT:
        return isinstance(value, int)
    if kind == PortKind.FLOAT:
        return isinstance(value, float)
    if kind == PortKind.BOOL:
        return isinstance(value, bool)
    if kind == PortKind.STRING:
        return isinstance(value, str)
    if kind == PortKind.QUANTITY:
        return matches_dimension(value, port.dimension)
    if kind == PortKind.STRUCTURE:
        return structure_registry.get_fullfilled_structure(
            _require_identifier(port)
        ).predicate(value)
    if kind == PortKind.MODEL:
        identifier = _require_identifier(port)
        try:
            fmodel = structure_registry.get_fullfilled_model(identifier)
        except KeyError:
            # Unregistered model: fall back to a structural check over children.
            if not port.children:
                raise ValueError(f"Port {identifier} has no children") from None
            return all(
                hasattr(value, child.key)
                and predicate_port(child, getattr(value, child.key), structure_registry)
                for child in port.children
            )
        return fmodel.predicate(value)
    if kind == PortKind.MEMORY_STRUCTURE:
        return structure_registry.get_fullfilled_memory_structure(
            _require_identifier(port)
        ).predicate(value)
    if kind == PortKind.ENUM:
        return structure_registry.get_fullfilled_enum(
            _require_identifier(port)
        ).predicate(value)

    raise ValueError(f"Unknown port kind: {port.kind} to predicate")


# Backwards-compatible names; both used to be separate, drifting copies.
predicate_port_input = predicate_port
predicate_serializable_port = predicate_port
