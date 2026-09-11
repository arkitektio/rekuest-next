"""Serialization for the actor side.

``expand_inputs``/``aexpand_arg`` turn incoming wire arguments into Python
values (resolving memory structures on the local shelve) and
``shrink_outputs``/``ashrink_return`` put results back on the wire. Each
``PortKind`` has one handler in :data:`ARG_EXPANDERS` / :data:`RETURN_SHRINKERS`.

The ``*_actor_*`` names are aliases of the shared implementations in
:mod:`.shrink` / :mod:`.expand`, used for dependency calls.
"""

import asyncio
import datetime as dt
from enum import Enum
from typing import Any, cast
from collections.abc import Sequence

from rath.scalars import ID

from rekuest_next.actors.types import Shelver
from rekuest_next.api.schema import (
    ArgPortInput,
    DefinitionInput,
    PortKind,
    ReturnPortInput,
)
from rekuest_next.constants import UNSET
from rekuest_next.scalars import Identifier
from rekuest_next.structures.errors import (
    ExpandingError,
    ShrinkingError,
    StructureExpandingError,
)
from rekuest_next.structures.quantities import expand_quantity, shrink_quantity
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.structures.serialization.context import (
    KindTable,
    SerializationContext,
    single_child,
    union_index,
)
from rekuest_next.structures.serialization.expand import (
    aexpand_return,
    aexpand_returns,
)
from rekuest_next.structures.serialization.port_errors import (
    to_port_error,
    to_shrink_port_error,
)
from rekuest_next.structures.serialization.predication import predicate_port
from rekuest_next.structures.serialization.protocols import SerializablePort
from rekuest_next.structures.serialization.shrink import ashrink_arg, ashrink_args
from rekuest_next.structures.types import JSONSerializable

# --------------------------------------------------------------------------- #
# Expanding incoming arguments
# --------------------------------------------------------------------------- #


def _expand_error(
    port: SerializablePort,
    value: Any,
    ctx: SerializationContext,
    message: str,  # noqa: ANN401
) -> ExpandingError:
    return to_port_error(port, value, message, path=ctx.path, depth=ctx.depth)


async def _expand(
    port: SerializablePort,
    value: Any,
    ctx: SerializationContext,  # noqa: ANN401
) -> Any:  # noqa: ANN401
    """Recursive entry point used by the container handlers."""
    return await aexpand_arg(
        port,
        value,
        structure_registry=ctx.registry,
        shelver=ctx.require_shelver(),
        path=ctx.path,
        depth=ctx.depth,
    )


async def _expand_dict(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> Any:  # noqa: ANN401
    child = single_child(port)
    if child is None:
        raise _expand_error(
            port,
            value,
            ctx,
            "The port must have exactly one child. This is not a valid dict port definition. Please report this to the developers.",
        )
    if not isinstance(value, dict):
        raise _expand_error(port, value, ctx, "We only accept dicts for dict ports")
    return {
        key: await _expand(child, item, ctx.child(port.key, key))
        for key, item in value.items()
    }


async def _expand_union(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> Any:  # noqa: ANN401
    if not port.children:
        raise _expand_error(
            port,
            value,
            ctx,
            "Can't expand value to union port. We only accept unions with children. Please report this to the developers.",
        )
    index, reason = union_index(value)
    if index is None:
        raise _expand_error(
            port, value, ctx, f"Can't expand value to union port. {reason}"
        )
    if not 0 <= index < len(port.children):
        raise _expand_error(
            port,
            value,
            ctx,
            f"Union '__use' index {index} is out of range for {len(port.children)} children.",
        )
    return await _expand(
        port.children[index], value["__value"], ctx.child(f"{port.key}[{index}]")
    )


async def _expand_list(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> Any:  # noqa: ANN401
    child = single_child(port)
    if child is None:
        raise _expand_error(
            port,
            value,
            ctx,
            "The port must have exactly one child. This is not a valid list port definition. Please report this to the developers.",
        )
    if not isinstance(value, list):
        raise _expand_error(port, value, ctx, "We only accept lists for list ports")
    return await asyncio.gather(
        *[
            _expand(child, item, ctx.child(f"{port.key}[{index}]"))
            for index, item in enumerate(value)
        ]
    )


async def _expand_model(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> Any:  # noqa: ANN401
    if not isinstance(value, dict):
        raise _expand_error(
            port,
            value,
            ctx,
            f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept dicts in models",
        )
    if not port.children:
        raise _expand_error(port, value, ctx, "We only accept models with children")
    if not port.identifier:
        raise _expand_error(port, value, ctx, "We only accept models with identifiers")

    expanded = await asyncio.gather(
        *[
            _expand(child, value.get(child.key, UNSET), ctx.child(port.key, child.key))
            for child in port.children
        ]
    )
    params = {child.key: val for child, val in zip(port.children, expanded)}
    fmodel = ctx.registry.get_fullfilled_model(identifier=port.identifier)
    return fmodel.cls(**params)


async def _expand_int(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> Any:  # noqa: ANN401
    if not isinstance(value, (int, float, str)):
        raise _expand_error(
            port,
            value,
            ctx,
            f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept ints, floats and strings",
        )
    return int(value)


async def _expand_float(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> Any:  # noqa: ANN401
    if not isinstance(value, (int, float, str)):
        raise _expand_error(
            port,
            value,
            ctx,
            f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept ints, floats and strings",
        )
    return float(value)


async def _expand_date(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> Any:  # noqa: ANN401
    if not isinstance(value, (str, dt.datetime)):
        raise _expand_error(
            port,
            value,
            ctx,
            f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept strings and datetime",
        )
    if isinstance(value, dt.datetime):
        return value
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


async def _expand_enum(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> Any:  # noqa: ANN401
    if port.identifier is None:
        raise _expand_error(port, value, ctx, "We only accept enums with identifiers")
    try:
        fenum = ctx.registry.get_fullfilled_enum(port.identifier)
    except KeyError:
        raise _expand_error(
            port, value, ctx, f"Enum {port.identifier} not found in registry"
        ) from None

    if isinstance(value, str):
        if value in fenum.cls.__members__:
            return fenum.cls[value]
        # Python 3.13+: partial() values are treated as descriptors so they
        # never appear in __members__. Fall back to a direct attribute lookup.
        attr = getattr(fenum.cls, value, None)
        if attr is not None:
            return attr
        raise _expand_error(
            port, value, ctx, f"Enum {port.identifier} does not have {value} as member"
        )
    if isinstance(value, int):
        if value not in fenum.cls.__members__.values():
            raise _expand_error(
                port,
                value,
                ctx,
                f"Enum {port.identifier} does not have {value} as member",
            )
        return fenum.cls(value)
    raise _expand_error(
        port,
        value,
        ctx,
        f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept strings and ints",
    )


def _unwrap_reference(
    port: SerializablePort,
    value: Any,
    ctx: SerializationContext,  # noqa: ANN401
) -> str:
    """Validate a ``{"__identifier", "object"}`` envelope and return the object id."""
    if not isinstance(value, dict):
        raise _expand_error(
            port,
            value,
            ctx,
            f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept dicts for structures",
        )
    if "__identifier" not in value:
        raise _expand_error(port, value, ctx, "Missing __identifier key in dict")
    if value["__identifier"] != port.identifier:
        raise _expand_error(
            port,
            value,
            ctx,
            f"Identifier mismatch: expected {port.identifier}, got {value['__identifier']}",
        )
    if "object" not in value:
        raise _expand_error(port, value, ctx, "Missing object key in dict")
    object = value["object"]
    if not isinstance(object, (str, int)):
        raise _expand_error(
            port, value, ctx, "We only accept strings and ints in the object key"
        )
    return str(object)


async def _expand_memory_structure(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> Any:  # noqa: ANN401
    drawer = _unwrap_reference(port, value, ctx)
    return await ctx.require_shelver().aget_from_shelve(drawer)


async def _expand_structure(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> Any:  # noqa: ANN401
    object = _unwrap_reference(port, value, ctx)
    if not port.identifier:
        raise _expand_error(
            port, value, ctx, "We only accept structures with identifiers"
        )
    fstruc = ctx.registry.get_fullfilled_structure(port.identifier)
    try:
        return await fstruc.aexpand(ID.validate(object))
    except Exception as e:
        raise _expand_error(
            port,
            value,
            ctx,
            f"Error expanding {repr(value)} with Structure {port.identifier}",
        ) from e


async def _expand_bool(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> Any:  # noqa: ANN401
    return bool(value)


async def _expand_string(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> Any:  # noqa: ANN401
    return str(value)


async def _expand_quantity(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> Any:  # noqa: ANN401
    try:
        return expand_quantity(value, port.reference_unit)
    except ValueError as e:
        raise _expand_error(port, value, ctx, str(e)) from e


ARG_EXPANDERS: KindTable = {
    PortKind.DICT: _expand_dict,
    PortKind.UNION: _expand_union,
    PortKind.LIST: _expand_list,
    PortKind.MODEL: _expand_model,
    PortKind.INT: _expand_int,
    PortKind.DATE: _expand_date,
    PortKind.FLOAT: _expand_float,
    PortKind.ENUM: _expand_enum,
    PortKind.MEMORY_STRUCTURE: _expand_memory_structure,
    PortKind.STRUCTURE: _expand_structure,
    PortKind.BOOL: _expand_bool,
    PortKind.STRING: _expand_string,
    PortKind.QUANTITY: _expand_quantity,
}


async def aexpand_arg(
    port: ArgPortInput | ReturnPortInput,
    value: JSONSerializable | UNSET,
    structure_registry: StructureRegistry,
    shelver: Shelver,
    *,
    path: Sequence[str] | None = None,
    depth: int = 0,
) -> Any:  # noqa: ANN401
    """Expand an incoming wire value through ``port``.

    ``None``/``UNSET`` fall back to the port default, then to ``None`` for
    nullable ports. Memory structures are resolved against ``shelver``.

    Raises:
        ExpandingError: If the value does not fit the port.
    """
    ctx = SerializationContext.build(structure_registry, shelver, path, depth)

    # Only arg ports carry a default.
    port_default = getattr(port, "default", None)

    if value is None:
        value = port_default

    if value is UNSET:
        if port_default is not UNSET:
            value = port_default
        elif port.nullable:
            return None
        else:
            raise _expand_error(
                port,
                value,
                ctx,
                "Port is required but no value was provided and no default is set",
            )

    if value is None:
        if port.nullable:
            return None
        raise _expand_error(
            port, value, ctx, "Port is not nullable (optional) but received None"
        )

    if not isinstance(value, (str, int, float, dict, list)):  # type: ignore[arg-type]
        raise _expand_error(
            port,
            value,
            ctx,
            "We only accept strings, ints and floats (json serializable) and null values",
        )

    handler = ARG_EXPANDERS.get(port.kind)
    if handler is None:
        raise StructureExpandingError(f"No expander for port kind {port.kind}")
    return await handler(port, value, ctx)


async def expand_inputs(
    definition: DefinitionInput,
    args: dict[str, JSONSerializable],
    structure_registry: StructureRegistry,
    shelver: Shelver,
    skip_expanding: bool = False,
) -> dict[str, Any]:
    """Expand an incoming ``args`` dict against ``definition.args``.

    Raises:
        ExpandingError: If any argument fails to expand.
    """
    if skip_expanding:
        return {port.key: args.get(port.key, None) for port in definition.args}

    try:
        expanded_args = await asyncio.gather(
            *[
                aexpand_arg(
                    port,
                    args.get(port.key, UNSET),
                    structure_registry=structure_registry,
                    shelver=shelver,
                    path=[port.key],
                    depth=1,
                )
                for port in definition.args
            ]
        )
    except Exception as e:
        raise ExpandingError(f"Couldn't expand Arguments: {e}") from e

    return {port.key: val for port, val in zip(definition.args, expanded_args)}


# --------------------------------------------------------------------------- #
# Shrinking outgoing returns
# --------------------------------------------------------------------------- #


def _shrink_error(
    port: SerializablePort,
    value: Any,
    ctx: SerializationContext,
    message: str,  # noqa: ANN401
) -> ShrinkingError:
    return to_shrink_port_error(
        port, value, message, path=(*ctx.path, port.key), depth=ctx.depth
    )


async def _shrink(
    port: SerializablePort,
    value: Any,
    ctx: SerializationContext,  # noqa: ANN401
) -> JSONSerializable:
    """Recursive entry point used by the container handlers."""
    return await ashrink_return(
        port,
        value,
        structure_registry=ctx.registry,
        shelver=ctx.require_shelver(),
        path=ctx.path,
        depth=ctx.depth,
    )


async def _shrink_union(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> JSONSerializable:  # noqa: ANN401
    if not port.children:
        raise _shrink_error(
            port,
            value,
            ctx,
            "Port is union but does not have children. Please report this to the developers.",
        )
    for index, possible_port in enumerate(port.children):
        if predicate_port(possible_port, value, ctx.registry):
            return {
                "__use": index,
                "__value": await _shrink(
                    possible_port, value, ctx.child(f"{port.key}[{index}]")
                ),
            }
    raise _shrink_error(
        port,
        value,
        ctx,
        f"Port is union but none of the predicates for this port held true. Children: {[c.key for c in port.children]}",
    )


async def _shrink_dict(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> JSONSerializable:  # noqa: ANN401
    if not isinstance(value, dict):
        raise _shrink_error(
            port,
            value,
            ctx,
            f"Port is dict but value is not a dict, got {type(value).__name__}",
        )
    child = single_child(port)
    if child is None:
        raise _shrink_error(
            port,
            value,
            ctx,
            f"Port is dict but has {len(port.children or [])} children (expected 1). Please report this to the developers.",
        )
    return {
        key: await _shrink(child, val, ctx.child(port.key, key))
        for key, val in value.items()
    }


async def _shrink_list(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> JSONSerializable:  # noqa: ANN401
    if not isinstance(value, list):
        raise _shrink_error(
            port,
            value,
            ctx,
            f"Port is list but value is not a list, got {type(value).__name__}",
        )
    child = single_child(port)
    if child is None:
        raise _shrink_error(
            port,
            value,
            ctx,
            f"Port is list but has {len(port.children or [])} children (expected 1). Please report this to the developers.",
        )
    return await asyncio.gather(
        *[
            _shrink(child, item, ctx.child(f"{port.key}[{index}]"))
            for index, item in enumerate(cast(list[Any], value))
        ]
    )


async def _shrink_model(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> JSONSerializable:  # noqa: ANN401
    if not port.children:
        raise _shrink_error(
            port,
            value,
            ctx,
            "Port is model but does not have children. Please report this to the developers.",
        )
    if not port.identifier:
        raise _shrink_error(
            port,
            value,
            ctx,
            "Port is model but does not have identifier. Please report this to the developers.",
        )
    shrunk = await asyncio.gather(
        *[
            _shrink(child, getattr(value, child.key), ctx.child(port.key, child.key))
            for child in port.children
        ]
    )
    params: dict[str, JSONSerializable] = {
        child.key: val for child, val in zip(port.children, shrunk)
    }
    params["__identifier"] = port.identifier
    return params


async def _shrink_int(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> JSONSerializable:  # noqa: ANN401
    if not isinstance(value, int):
        raise _shrink_error(
            port, value, ctx, f"Expected int, got {type(value).__name__}: {repr(value)}"
        )
    return int(value)


async def _shrink_float(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> JSONSerializable:  # noqa: ANN401
    if not isinstance(value, (float, int)):
        raise _shrink_error(
            port,
            value,
            ctx,
            f"Expected float (or int), got {type(value).__name__}: {repr(value)}",
        )
    return float(value)


async def _shrink_date(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> JSONSerializable:  # noqa: ANN401
    if not isinstance(value, dt.datetime):
        raise _shrink_error(
            port,
            value,
            ctx,
            f"Expected datetime, got {type(value).__name__}: {repr(value)}",
        )
    return value.isoformat()


async def _shrink_memory_structure(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> JSONSerializable:  # noqa: ANN401
    if not port.identifier:
        raise _shrink_error(
            port,
            value,
            ctx,
            "Port is memory structure but does not have identifier. Please report this to the developers.",
        )
    drawer = await ctx.require_shelver().aput_on_shelve(
        Identifier.validate(port.identifier), value
    )
    return {"__identifier": port.identifier, "object": drawer}


async def _shrink_structure(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> JSONSerializable:  # noqa: ANN401
    if not port.identifier:
        raise _shrink_error(
            port,
            value,
            ctx,
            "Port is structure but does not have identifier. Please report this to the developers.",
        )
    fstruc = ctx.registry.get_fullfilled_structure(port.identifier)
    try:
        shrunk = await fstruc.ashrink(value)
    except Exception as e:
        raise _shrink_error(
            port,
            value,
            ctx,
            f"Error shrinking with Structure {port.identifier}: {str(e)}",
        ) from e
    return {"__identifier": port.identifier, "object": shrunk}


async def _shrink_bool(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> JSONSerializable:  # noqa: ANN401
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
        raise _shrink_error(
            port,
            value,
            ctx,
            f"Can't shrink string '{value}' to bool. We only accept 'true' or 'false'",
        )
    if isinstance(value, int):
        if value in (0, 1):
            return bool(value)
        raise _shrink_error(
            port, value, ctx, f"Can't shrink int {value} to bool. We only accept 0 or 1"
        )
    raise _shrink_error(
        port,
        value,
        ctx,
        f"Expected bool, str, or int, got {type(value).__name__}: {repr(value)}",
    )


async def _shrink_string(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> JSONSerializable:  # noqa: ANN401
    if not isinstance(value, str):
        raise _shrink_error(
            port, value, ctx, f"Expected str, got {type(value).__name__}: {repr(value)}"
        )
    return str(value)


async def _shrink_quantity(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> JSONSerializable:  # noqa: ANN401
    return shrink_quantity(value)


async def _shrink_enum(
    port: SerializablePort, value: Any, ctx: SerializationContext
) -> JSONSerializable:  # noqa: ANN401
    if isinstance(value, Enum):
        return value.name
    # typing.Literal-derived enums carry bare values (e.g. "a" or 1) instead of
    # Enum members, so accept a value that names a valid choice.
    candidate = str(value)
    if any(candidate == choice.value for choice in (port.choices or [])):
        return candidate
    raise _shrink_error(
        port,
        value,
        ctx,
        f"Expected Enum or one of {[c.value for c in port.choices or []]}, "
        f"got {type(value).__name__}: {repr(value)}",
    )


RETURN_SHRINKERS: KindTable = {
    PortKind.UNION: _shrink_union,
    PortKind.DICT: _shrink_dict,
    PortKind.LIST: _shrink_list,
    PortKind.MODEL: _shrink_model,
    PortKind.INT: _shrink_int,
    PortKind.FLOAT: _shrink_float,
    PortKind.DATE: _shrink_date,
    PortKind.MEMORY_STRUCTURE: _shrink_memory_structure,
    PortKind.STRUCTURE: _shrink_structure,
    PortKind.BOOL: _shrink_bool,
    PortKind.STRING: _shrink_string,
    PortKind.QUANTITY: _shrink_quantity,
    PortKind.ENUM: _shrink_enum,
}


async def ashrink_return(
    port: ReturnPortInput,
    value: Any,  # noqa: ANN401
    structure_registry: StructureRegistry,
    shelver: Shelver,
    *,
    path: Sequence[str] | None = None,
    depth: int = 0,
) -> JSONSerializable:
    """Shrink an outgoing Python value through ``port``.

    Memory structures are parked on ``shelver`` and replaced by a reference.

    Raises:
        ShrinkingError: If the value does not fit the port.
    """
    ctx = SerializationContext.build(structure_registry, shelver, path, depth)
    try:
        if value is None:
            if port.nullable:
                return None
            raise _shrink_error(
                port,
                value,
                ctx,
                f"Port {port.key} is not nullable (optional) but received None",
            )

        handler = RETURN_SHRINKERS.get(port.kind)
        if handler is None:
            raise _shrink_error(port, value, ctx, f"Unsupported port kind: {port.kind}")
        return await handler(port, value, ctx)

    except ShrinkingError:
        raise
    except Exception as e:
        raise _shrink_error(port, value, ctx, f"Unexpected error: {str(e)}") from e


async def shrink_outputs(
    definition: DefinitionInput,
    returns: list[Any] | None,
    structure_registry: StructureRegistry,
    shelver: Shelver,
    skip_shrinking: bool = False,
) -> dict[str, JSONSerializable]:
    """Shrink a function's return value(s) against ``definition.returns``.

    A single (non-tuple) return is treated as one output; a tuple is spread
    over the return ports in order.
    """
    if returns is None:
        returns = []
    elif not isinstance(returns, tuple):
        returns = [returns]

    assert len(definition.returns) == len(returns), (
        f"Mismatch in Return Length: expected {len(definition.returns)} got {len(returns)}"
    )

    if skip_shrinking:
        return {port.key: val for port, val in zip(definition.returns, returns)}

    shrunk = await asyncio.gather(
        *[
            ashrink_return(
                port, val, structure_registry, shelver=shelver, path=[port.key], depth=0
            )
            for port, val in zip(definition.returns, returns)
        ]
    )
    return {port.key: val for port, val in zip(definition.returns, shrunk)}


# --------------------------------------------------------------------------- #
# Dependency-call aliases (shared with the postman path)
# --------------------------------------------------------------------------- #

ashrink_actor_arg = ashrink_arg
ashrink_actor_args = ashrink_args
aexpand_actor_return = aexpand_return
aexpand_actor_returns = aexpand_returns

__all__ = [
    "aexpand_arg",
    "expand_inputs",
    "ashrink_return",
    "shrink_outputs",
    "ashrink_actor_arg",
    "ashrink_actor_args",
    "aexpand_actor_return",
    "aexpand_actor_returns",
    "ARG_EXPANDERS",
    "RETURN_SHRINKERS",
]
