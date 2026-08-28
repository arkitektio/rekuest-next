"""Shrinking: turn Python values into JSON-serializable wire values.

Shared by the postman (client → server) and actor (dependency call) paths,
which used to carry drifting copies of this logic. Each ``PortKind`` has one
handler in :data:`SHRINKERS`; container kinds recurse through
:func:`ashrink_arg`.
"""

import asyncio
from enum import Enum
from typing import Any, cast
from collections.abc import Sequence

from rekuest_next.api.schema import Action, DefinitionInput, PortKind
from rekuest_next.structures.errors import (
    PortShrinkingError,
    ShrinkingError,
    StructureShrinkingError,
)
from rekuest_next.structures.quantities import shrink_quantity
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.structures.serialization.context import (
    KindTable,
    SerializationContext,
    single_child,
)
from rekuest_next.structures.serialization.memory import shrink_memory_reference
from rekuest_next.structures.serialization.predication import predicate_port
from rekuest_next.structures.serialization.protocols import SerializablePort
from rekuest_next.structures.types import JSONSerializable


async def _shrink(
    port: SerializablePort,
    value: Any,
    ctx: SerializationContext,  # noqa: ANN401
) -> JSONSerializable:
    """Recursive entry point used by the container handlers."""
    return await ashrink_arg(port, value, structure_registry=ctx.registry)


async def _dict(
    port: SerializablePort,
    value: Any,
    ctx: SerializationContext,  # noqa: ANN401
) -> JSONSerializable:
    if not isinstance(value, dict):
        raise ShrinkingError(f"Expected value to be a dict, but got {type(value)}")
    if not all(isinstance(k, str) for k in value.keys()):  # type: ignore[union-attr]
        raise ShrinkingError(f"Expected all keys to be strings, but got {value.keys()}")
    child = single_child(port)
    if child is None:
        raise ShrinkingError(
            f"Port {port} must have exactly one child, but value is a dict"
        )
    return {
        key: await _shrink(child, item, ctx.child(port.key, key))
        for key, item in value.items()  # type: ignore[union-attr]
    }


async def _list(
    port: SerializablePort,
    value: Any,
    ctx: SerializationContext,  # noqa: ANN401
) -> JSONSerializable:
    if not isinstance(value, list):
        raise ShrinkingError(f"Expected value to be a list, but got {type(value)}")
    child = single_child(port)
    if child is None:
        raise ShrinkingError(
            f"Port {port} must have exactly one child, but value is a list"
        )
    return await asyncio.gather(
        *[
            _shrink(child, item, ctx.child(f"{port.key}[{index}]"))
            for index, item in enumerate(cast(list[Any], value))
        ]
    )


async def _union(
    port: SerializablePort,
    value: Any,
    ctx: SerializationContext,  # noqa: ANN401
) -> JSONSerializable:
    if not port.children:
        raise ShrinkingError(f"Port {port} is a union but has no children")
    for index, possible_port in enumerate(port.children):
        if predicate_port(possible_port, value, ctx.registry):
            return {
                "__use": index,
                "__value": await _shrink(
                    possible_port, value, ctx.child(f"{port.key}[{index}]")
                ),
            }
    raise ShrinkingError(
        f"Port is union but none of the predicates for this port held true {port.children}"
    )


async def _model(
    port: SerializablePort,
    value: Any,
    ctx: SerializationContext,  # noqa: ANN401
) -> JSONSerializable:
    if not port.identifier:
        raise ShrinkingError(f"Port {port} is a model but has no identifier")
    if not port.children:
        raise ShrinkingError(f"Port {port} is a model but has no children")
    try:
        shrunk = await asyncio.gather(
            *[
                _shrink(
                    child, getattr(value, child.key), ctx.child(port.key, child.key)
                )
                for child in port.children
            ]
        )
    except Exception as e:
        raise PortShrinkingError(f"Couldn't shrink Children {port.children}") from e
    params: dict[str, Any] = {
        child.key: val for child, val in zip(port.children, shrunk)
    }
    params["__identifier"] = port.identifier
    return params


async def _enum(
    port: SerializablePort,
    value: Any,
    ctx: SerializationContext,  # noqa: ANN401
) -> JSONSerializable:
    if port.identifier is None:
        raise ShrinkingError(f"Port {port} is an enum but has no identifier")
    if isinstance(value, Enum):
        value = value.name
    if not isinstance(value, str):
        raise ShrinkingError(
            f"Expected value o be a string or enum, but got {type(value)}"
        )
    if not port.choices:
        raise ShrinkingError(f"Port {port} is an enum but has no choices")
    if not any(value == choice.value for choice in port.choices):
        raise ShrinkingError(f"Expected value to be in {port.choices}, but got {value}")
    return value


async def _memory_structure(
    port: SerializablePort,
    value: Any,
    ctx: SerializationContext,  # noqa: ANN401
) -> JSONSerializable:
    return shrink_memory_reference(port, value)


async def _structure(
    port: SerializablePort,
    value: Any,
    ctx: SerializationContext,  # noqa: ANN401
) -> JSONSerializable:
    if not port.identifier:
        raise ShrinkingError(f"Port {port} is a structure but has no identifier")
    if isinstance(value, str):
        # A bare string is taken as a reference to a global structure.
        return value
    fstruc = ctx.registry.get_fullfilled_structure(port.identifier)
    try:
        shrunk = await fstruc.ashrink(value)
    except Exception:
        raise StructureShrinkingError(
            f"Error shrinking {repr(value)} with Structure {port.identifier}"
        ) from None
    return {"__identifier": port.identifier, "object": str(shrunk)}


async def _float(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> JSONSerializable:  # noqa: ANN401
    return float(value)


async def _int(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> JSONSerializable:  # noqa: ANN401
    return int(value)


async def _date(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> JSONSerializable:  # noqa: ANN401
    return value.isoformat()


async def _bool(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> JSONSerializable:  # noqa: ANN401
    return bool(value)


async def _string(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> JSONSerializable:  # noqa: ANN401
    return str(value)


async def _quantity(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> JSONSerializable:  # noqa: ANN401
    return shrink_quantity(value)


SHRINKERS: KindTable = {
    PortKind.DICT: _dict,
    PortKind.LIST: _list,
    PortKind.UNION: _union,
    PortKind.MODEL: _model,
    PortKind.ENUM: _enum,
    PortKind.MEMORY_STRUCTURE: _memory_structure,
    PortKind.STRUCTURE: _structure,
    PortKind.FLOAT: _float,
    PortKind.INT: _int,
    PortKind.DATE: _date,
    PortKind.BOOL: _bool,
    PortKind.STRING: _string,
    PortKind.QUANTITY: _quantity,
}


async def ashrink_arg(
    port: SerializablePort,
    value: Any,  # noqa: ANN401
    structure_registry: StructureRegistry,
) -> JSONSerializable:
    """Shrink a Python value into its JSON wire form through ``port``.

    Raises:
        ShrinkingError: If the value does not fit the port.
    """
    try:
        if value is None:
            if port.nullable:
                return None
            raise ShrinkingError(
                f"{port} is not nullable (optional) but your provided None"
            )

        handler = SHRINKERS.get(port.kind)
        if handler is None:
            raise NotImplementedError(f"No shrinker for port kind {port.kind} ({port})")
        return await handler(
            port, value, SerializationContext.build(structure_registry)
        )

    except ShrinkingError:
        raise
    except Exception as e:
        raise PortShrinkingError(
            f"Couldn't shrink value {value} with port {port}"
        ) from e


async def ashrink_args(
    definition: DefinitionInput | Action,
    args: Sequence[Any],
    kwargs: dict[str, Any],
    structure_registry: StructureRegistry,
) -> dict[str, JSONSerializable]:
    """Shrink positional and keyword arguments against ``definition.args``.

    Positional ``args`` are consumed first in port order, then ``kwargs`` are
    looked up by port key. A missing value is only tolerated for nullable ports
    or ports with a default (the agent fills defaults in on expansion).

    Raises:
        ShrinkingError: If ``args`` is not iterable, a required value is
            missing, or an element fails to shrink.
    """
    try:
        args_iterator = iter(args)
    except TypeError as e:
        raise ShrinkingError(f"Couldn't iterate over args {args}") from e

    shrinked_kwargs: dict[str, JSONSerializable] = {}

    for port in definition.args:
        try:
            arg = next(args_iterator)
        except StopIteration as e:
            if port.key in kwargs:
                arg = kwargs[port.key]
            elif port.nullable or port.default is not None:
                arg = None  # defaults will be set by the agent
            else:
                raise ShrinkingError(
                    f"Couldn't find value for nonnunllable port {port.key}"
                ) from e

        try:
            shrinked_kwargs[port.key] = await ashrink_arg(
                port, arg, structure_registry=structure_registry
            )
        except Exception as e:
            raise ShrinkingError(f"Couldn't shrink arg {arg} with port {port}") from e

    return shrinked_kwargs
