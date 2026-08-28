"""Expanding: turn JSON wire values back into Python values.

Shared by the postman (server → client) and actor (dependency call) paths,
which used to carry drifting copies of this logic. Each ``PortKind`` has one
handler in :data:`EXPANDERS`; container kinds recurse through
:func:`aexpand_return`.
"""

import asyncio
import datetime as dt
from typing import Any
from collections.abc import Sequence

from rath.scalars import ID

from rekuest_next.api.schema import Action, DefinitionInput, PortKind
from rekuest_next.structures.errors import (
    ExpandingError,
    PortExpandingError,
    StructureExpandingError,
)
from rekuest_next.structures.quantities import expand_quantity
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.structures.serialization.context import (
    KindTable,
    SerializationContext,
    single_child,
    union_index,
)
from rekuest_next.structures.serialization.memory import expand_memory_reference
from rekuest_next.structures.serialization.port_errors import to_port_error
from rekuest_next.structures.serialization.protocols import SerializablePort
from rekuest_next.structures.types import JSONSerializable


async def _expand(
    port: SerializablePort,
    value: Any,
    ctx: SerializationContext,  # noqa: ANN401
) -> Any:  # noqa: ANN401
    """Recursive entry point used by the container handlers."""
    return await aexpand_return(
        port, value, structure_registry=ctx.registry, path=ctx.path, depth=ctx.depth
    )


async def _dict(port: SerializablePort, value: Any, ctx: SerializationContext) -> Any:  # noqa: ANN401
    if not isinstance(value, dict):
        raise PortExpandingError(f"Expected value to be a dict, but got {type(value)}")
    child = single_child(port)
    if child is None:
        raise PortExpandingError(f"Port {port.identifier} must have exactly one child")
    return {
        key: await _expand(child, item, ctx.child(port.key, key))
        for key, item in value.items()
    }


async def _list(port: SerializablePort, value: Any, ctx: SerializationContext) -> Any:  # noqa: ANN401
    if not isinstance(value, list):
        raise PortExpandingError(f"Expected value to be a list, but got {type(value)}")
    child = single_child(port)
    if child is None:
        raise PortExpandingError(f"Port {port.identifier} must have exactly one child")
    return await asyncio.gather(
        *[
            _expand(child, item, ctx.child(f"{port.key}[{index}]"))
            for index, item in enumerate(value)
        ]
    )


async def _union(port: SerializablePort, value: Any, ctx: SerializationContext) -> Any:  # noqa: ANN401
    if not port.children:
        raise PortExpandingError(f"Port {port.identifier} has no children")
    index, reason = union_index(value)
    if index is None:
        raise PortExpandingError(reason or "Invalid union value")
    if not 0 <= index < len(port.children):
        raise PortExpandingError(
            f"Union '__use' index {index} is out of range for {len(port.children)} children"
        )
    return await _expand(
        port.children[index], value["__value"], ctx.child(f"{port.key}[{index}]")
    )


async def _int(port: SerializablePort, value: Any, ctx: SerializationContext) -> Any:  # noqa: ANN401
    if not isinstance(value, (int, str)):
        raise PortExpandingError(
            f"Expected value to be an int or str, but got {type(value)}"
        )
    return int(value)


async def _float(port: SerializablePort, value: Any, ctx: SerializationContext) -> Any:  # noqa: ANN401
    if not isinstance(value, (float, str)):
        raise PortExpandingError(
            f"Expected value to be a float or str, but got {type(value)}"
        )
    return float(value)


async def _date(port: SerializablePort, value: Any, ctx: SerializationContext) -> Any:  # noqa: ANN401
    if not isinstance(value, str):
        raise PortExpandingError(
            f"Expected value to be a string, but got {type(value)}"
        )
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


async def _memory_structure(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> Any:  # noqa: ANN401
    return expand_memory_reference(port, value)


async def _structure(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> Any:  # noqa: ANN401
    def error(message: str) -> ExpandingError:
        return to_port_error(port, value, message, path=ctx.path, depth=ctx.depth)

    if not port.identifier:
        raise error("Port is a structure but has no identifier")
    if not isinstance(value, dict):
        raise error(
            f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept dicts for structures"
        )
    if "__identifier" not in value:
        raise error(
            f"Can't expand {value} to {port.kind}. Missing __identifier key in dict"
        )
    if value["__identifier"] != port.identifier:
        raise error(
            f"Identifier mismatch: expected {port.identifier}, got {value['__identifier']}"
        )
    if "object" not in value:
        raise error(f"Can't expand {value} to {port.kind}. Missing object key in dict")
    object = value["object"]
    if not isinstance(object, (str, int)):
        raise error(f"Expected object to be a string or int, but got {type(object)}")

    try:
        fstruc = ctx.registry.get_fullfilled_structure(port.identifier)
    except KeyError as e:
        raise PortExpandingError(
            f"Structure {port.identifier} not found. Was it ever registered?"
        ) from e
    try:
        return await fstruc.aexpand(ID.validate(object))
    except Exception:
        raise StructureExpandingError(
            f"Error expanding {repr(value)} with Structure {port.identifier}"
        ) from None


async def _model(port: SerializablePort, value: Any, ctx: SerializationContext) -> Any:  # noqa: ANN401
    if not isinstance(value, dict):
        raise PortExpandingError(f"Expected value to be a dict, but got {type(value)}")
    if not port.children:
        raise PortExpandingError(
            f"Port {port.identifier} is a model but has no children"
        )
    if not port.identifier:
        raise PortExpandingError(f"Port {port.key} is a model but has no identifier")
    expanded = await asyncio.gather(
        *[
            _expand(child, value.get(child.key), ctx.child(port.key, child.key))
            for child in port.children
        ]
    )
    params = {child.key: val for child, val in zip(port.children, expanded)}
    try:
        fmodel = ctx.registry.get_fullfilled_model(port.identifier)
    except KeyError as e:
        raise PortExpandingError(
            f"Model {port.identifier} not found. Was it ever registered?"
        ) from e
    return fmodel.cls(**params)


async def _enum(port: SerializablePort, value: Any, ctx: SerializationContext) -> Any:  # noqa: ANN401
    if not port.identifier:
        raise PortExpandingError(f"Port {port.key} is an enum but has no identifier")
    try:
        fenum = ctx.registry.get_fullfilled_enum(port.identifier)
    except KeyError as e:
        raise PortExpandingError(
            f"Enum {port.identifier} not found. Was it ever registered?"
        ) from e
    if isinstance(value, str):
        if value in fenum.cls.__members__:
            return fenum.cls[value]
        attr = getattr(fenum.cls, value, None)  # partial() members on 3.13+
        if attr is not None:
            return attr
        raise PortExpandingError(
            f"Enum {port.identifier} does not have {value} as member"
        )
    if isinstance(value, int):
        return fenum.cls(value)
    raise PortExpandingError(
        f"Expected enum value to be a str or int, but got {type(value)}"
    )


async def _bool(port: SerializablePort, value: Any, ctx: SerializationContext) -> Any:  # noqa: ANN401
    return bool(value)


async def _string(port: SerializablePort, value: Any, ctx: SerializationContext) -> Any:  # noqa: ANN401
    return str(value)


async def _quantity(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> Any:  # noqa: ANN401
    return expand_quantity(value, port.reference_unit)


EXPANDERS: KindTable = {
    PortKind.DICT: _dict,
    PortKind.LIST: _list,
    PortKind.UNION: _union,
    PortKind.INT: _int,
    PortKind.FLOAT: _float,
    PortKind.DATE: _date,
    PortKind.MEMORY_STRUCTURE: _memory_structure,
    PortKind.STRUCTURE: _structure,
    PortKind.MODEL: _model,
    PortKind.ENUM: _enum,
    PortKind.BOOL: _bool,
    PortKind.STRING: _string,
    PortKind.QUANTITY: _quantity,
}


async def aexpand_return(
    port: SerializablePort,
    value: JSONSerializable,
    structure_registry: StructureRegistry,
    path: Sequence[str] | None = None,
    depth: int = 0,
) -> Any:  # noqa: ANN401
    """Expand a JSON wire value back into a Python value through ``port``.

    Raises:
        ExpandingError: If the value does not fit the port.
    """
    if value is None:
        if port.nullable:
            return None
        raise PortExpandingError(
            f"{port.key} is not nullable (optional) but your provided None"
        )

    handler = EXPANDERS.get(port.kind)
    if handler is None:
        raise StructureExpandingError(f"No valid expander found for {port.kind}")
    return await handler(
        port,
        value,
        SerializationContext.build(structure_registry, path=path, depth=depth),
    )


async def aexpand_returns(
    definition: DefinitionInput | Action,
    returns: dict[str, JSONSerializable],
    structure_registry: StructureRegistry,
) -> tuple[Any, ...]:
    """Expand a returns dict against ``definition.returns``, in port order.

    A key missing from ``returns`` is tolerated only for nullable ports.

    Raises:
        ExpandingError: If a required key is missing or an element fails to
            expand.
    """
    assert returns is not None, "Returns can't be empty"

    expanded_returns: list[Any] = []

    for port in definition.returns:
        if port.key not in returns:
            if not port.nullable:
                raise ExpandingError(f"Missing key {port.key} in returns")
            expanded_returns.append(None)
            continue

        try:
            expanded_returns.append(
                await aexpand_return(
                    port, returns[port.key], structure_registry=structure_registry
                )
            )
        except Exception as e:
            raise ExpandingError(
                f"Couldn't expand the reutrn value `{returns[port.key]}` for port {port.key}"
            ) from e

    return tuple(expanded_returns)
