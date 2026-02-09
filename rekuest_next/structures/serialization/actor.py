"""Serialization and deserialization function for actors"""

from enum import Enum
from typing import Any, Dict, List, cast
import asyncio
from rekuest_next.scalars import Identifier
from rath.scalars import ID
from rekuest_next.structures.errors import ExpandingError, ShrinkingError
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.api.schema import (
    PortKind,
    PortInput,
    DefinitionInput,
)
from rekuest_next.structures.errors import (
    PortShrinkingError,
    StructureShrinkingError,
    StructureExpandingError,
)
from rekuest_next.actors.types import Shelver
from rekuest_next.structures.types import JSONSerializable
from .predication import predicate_port_input
import datetime as dt
from typing import Sequence, Tuple

from rekuest_next.api.schema import ChildPortNestedChildren

from rekuest_next.structures.errors import (
    PortExpandingError,
)
from .predication import predicate_serializable_port
from rekuest_next.constants import UNSET


def _format_path_tree(path: Sequence[str] | None) -> str:
    if not path:
        return "- <root>"
    lines = []
    for depth, part in enumerate(path):
        indent = "  " * depth
        lines.append(f"{indent}- {part}")
    return "\n".join(lines)


def to_shrink_port_error(
    port: PortInput,
    value: Any,
    message: str,
    *,
    path: Sequence[str] | None = None,
    depth: int | None = None,
) -> ShrinkingError:
    """Helper function to create a ShrinkingError with port context."""
    depth_info = f"Depth: {depth}" if depth is not None else "Depth: unknown"
    tree_info = _format_path_tree(path)
    return ShrinkingError(
        "Error shrinking value with nested path:\n"
        f"{tree_info}\n"
        f"Port: {port.key} ({port.kind})\n"
        f"{depth_info}\n"
        f"Reason: {message}"
    )


def to_port_error(
    port: PortInput,
    value: Any,
    message: str,
    *,
    path: Sequence[str] | None = None,
    depth: int | None = None,
) -> ExpandingError:
    """Helper function to create an ExpandingError with port context."""
    depth_info = f"Depth: {depth}" if depth is not None else "Depth: unknown"
    tree_info = _format_path_tree(path)
    return ExpandingError(
        "Error expanding value with nested path:\n"
        f"{tree_info}\n"
        f"Port: {port.key} ({port.kind})\n"
        f"{depth_info}\n"
        f"Reason: {message}"
    )


async def aexpand_arg(
    port: PortInput,
    value: JSONSerializable | UNSET,
    structure_registry: StructureRegistry,
    shelver: Shelver,
    *,
    path: Sequence[str] | None = None,
    depth: int = 0,
) -> Any:  # noqa: ANN401
    """Expand a value through a port

    Args:
        port (ArgPort): Port to expand to
        value (Any): Value to expand
    Returns:
        Any: Expanded value

    """
    if value is None:
        value = port.default

    if value is UNSET:
        if port.default is not UNSET:
            value = port.default
        elif port.nullable:
            return None
        else:
            raise to_port_error(
                port,
                value,
                "Port is required but no value was provided and no default is set",
                path=[*(path or []), port.key] if path is not None else [port.key],
                depth=depth,
            )

    if value is None:
        if port.nullable:
            return None
        else:
            raise to_port_error(
                port,
                value,
                "Port is not nullable (optional) but received None",
                path=[*(path or []), port.key] if path is not None else [port.key],
                depth=depth,
            )

    if not isinstance(value, (str, int, float, dict, list)):  # type: ignore
        raise to_port_error(
            port,
            value,
            "We only accept strings, ints and floats (json serializable) and null values",
            path=path,
            depth=depth,
        )

    if port.kind == PortKind.DICT:
        if not port.children:
            raise to_port_error(
                port,
                value,
                "The port has no children. This is not a valid dict port definition. Please report this to the developers.",
                path=path,
                depth=depth,
            )

        expanding_port = port.children[0]

        if not isinstance(value, dict):
            raise to_port_error(
                port,
                value,
                "We only accept dicts for dict ports",
                path=path,
                depth=depth,
            )

        return {
            key: await aexpand_arg(
                expanding_port,
                value,
                structure_registry=structure_registry,
                shelver=shelver,
                path=[*(path or []), port.key, key]
                if path is not None
                else [port.key, key],
                depth=depth + 1,
            )
            for key, value in value.items()
        }

    if port.kind == PortKind.UNION:
        if not port.children:
            raise to_port_error(
                port,
                value,
                "Can't expand value to union port. We only accept unions with children. Please report this to the developers.",
                path=path,
                depth=depth,
            )

        if not isinstance(value, dict):
            raise to_port_error(
                port,
                value,
                "Can't expand value to union port. We only accept dicts in unions. Please report this to the developers.",
                path=path,
                depth=depth,
            )

        assert "use" in value, "No use in vaalue"
        index = value["use"]
        true_value = value["value"]

        if isinstance(index, str):
            index = int(index)

        if not isinstance(index, int):
            raise to_port_error(
                port,
                value,
                "Can't expand value to union port. We only accept ints in as index in unions. Please report this to the developers.",
                path=path,
                depth=depth,
            )
        try:
            child = port.children[index]
        except IndexError as e:
            raise to_port_error(
                port,
                value,
                f"The index {index} is out of range for this union port which has {len(port.children)} children.",
                path=path,
                depth=depth,
            ) from e

        return await aexpand_arg(
            child,
            true_value,
            structure_registry=structure_registry,
            shelver=shelver,
            path=[*(path or []), f"{port.key}[{index}]"]
            if path is not None
            else [f"{port.key}[{index}]"],
            depth=depth + 1,
        )

    if port.kind == PortKind.LIST:
        if not port.children:
            raise to_port_error(
                port,
                value,
                "The port has no children. This is not a valid list port definition. Please report this to the developers.",
                path=path,
                depth=depth,
            ) from None

        expanding_port = port.children[0]

        if not isinstance(value, list):
            raise to_port_error(
                port,
                value,
                "We only accept lists for list ports",
                path=path,
                depth=depth,
            ) from None

        return await asyncio.gather(
            *[
                aexpand_arg(
                    expanding_port,
                    item,
                    structure_registry=structure_registry,
                    shelver=shelver,
                    path=[*(path or []), f"{port.key}[{index}]"]
                    if path is not None
                    else [f"{port.key}[{index}]"],
                    depth=depth + 1,
                )
                for index, item in enumerate(value)
            ]
        )

    if port.kind == PortKind.MODEL:
        children = port.children
        identifier = port.identifier
        if not isinstance(value, dict):
            raise to_port_error(
                port,
                value,
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                " dicts in models",
                path=path,
                depth=depth,
            )
        if not children:
            raise to_port_error(
                port,
                value,
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                " models with children",
                path=path,
                depth=depth,
            )
        if not identifier:
            raise to_port_error(
                port,
                value,
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                " models with identifiers",
                path=path,
                depth=depth,
            )

        expanded_args = await asyncio.gather(
            *[
                aexpand_arg(
                    port,
                    value.get(port.key, UNSET),
                    structure_registry=structure_registry,
                    shelver=shelver,
                    path=[*(path or []), port.key] if path is not None else [port.key],
                    depth=depth + 1,
                )
                for port in children
            ]
        )
        expandend_params = {port.key: val for port, val in zip(children, expanded_args)}

        fmodel = structure_registry.get_fullfilled_model(identifier=identifier)
        return fmodel.cls(**expandend_params)

    if port.kind == PortKind.INT:
        if not isinstance(value, (int, float, str)):
            raise to_port_error(
                port,
                value,
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                " ints, floats and strings",
                path=path,
                depth=depth,
            ) from None
        return int(value)

    if port.kind == PortKind.DATE:
        if not isinstance(value, (str, dt.datetime)):
            raise to_port_error(
                port,
                value,
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                " strings and datetime",
                path=path,
                depth=depth,
            ) from None
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))

    if port.kind == PortKind.FLOAT:
        if not isinstance(value, (int, float, str)):
            raise to_port_error(
                port,
                value,
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                " ints, floats and strings",
                path=path,
                depth=depth,
            ) from None
        return float(value)

    if port.kind == PortKind.ENUM:
        if port.identifier is None:
            raise to_port_error(
                port,
                value,
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                " enums with identifiers",
                path=path,
                depth=depth,
            ) from None

        fenum = structure_registry.get_fullfilled_enum(port.identifier)
        if fenum:
            if isinstance(value, str):
                if value not in fenum.cls.__members__:
                    raise to_port_error(
                        port,
                        value,
                        f"Enum {port.identifier} does not have {value} as member",
                        path=path,
                        depth=depth,
                    )
                return fenum.cls[value]
            if isinstance(value, int):
                if value not in fenum.cls.__members__.values():
                    raise to_port_error(
                        port,
                        value,
                        f"Enum {port.identifier} does not have {value} as member",
                        path=path,
                        depth=depth,
                    )
                return fenum.cls(value)
            else:
                raise to_port_error(
                    port,
                    value,
                    f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                    " strings and ints",
                    path=path,
                    depth=depth,
                ) from None

        else:
            raise to_port_error(
                port,
                value,
                f"Enum {port.identifier} not found in registry",
                path=path,
                depth=depth,
            )

    if port.kind == PortKind.MEMORY_STRUCTURE:
        if not isinstance(value, (str, int)):
            raise to_port_error(
                port,
                value,
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                " strings and ints",
                path=path,
                depth=depth,
            ) from None

        if isinstance(value, int):
            value = str(value)

        return await shelver.aget_from_shelve(value)

    if port.kind == PortKind.STRUCTURE:
        if not isinstance(value, (str, int)):
            raise to_port_error(
                port,
                value,
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                " strings and ints",
            ) from None

        if isinstance(value, int):
            value = str(value)

        if not port.identifier:
            raise to_port_error(
                port,
                value,
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                " structures with identifiers",
                path=path,
                depth=depth,
            ) from None

        fstruc = structure_registry.get_fullfilled_structure(port.identifier)

        try:
            expanded = await fstruc.aexpand(ID.validate(value))
            return expanded
        except Exception as e:
            raise to_port_error(
                port,
                value,
                f"Error expanding {repr(value)} with Structure {port.identifier}",
                path=path,
                depth=depth,
            ) from e

    if port.kind == PortKind.BOOL:
        return bool(value)

    if port.kind == PortKind.STRING:
        return str(value)

    raise StructureExpandingError(f"No shrinker for port kind {port.kind}")


async def expand_inputs(
    definition: DefinitionInput,
    args: Dict[str, JSONSerializable],
    structure_registry: StructureRegistry,
    shelver: Shelver,
    skip_expanding: bool = False,
) -> Dict[str, Any]:
    """Expand

    Args:
        action (Action): [description]
        args (List[Any]): [description]
        kwargs (List[Any]): [description]
        registry (Registry): [description]
    """

    expanded_args = []

    if not skip_expanding:
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

            expandend_params = {
                port.key: val for port, val in zip(definition.args, expanded_args)
            }

        except Exception as e:
            raise ExpandingError(f"Couldn't expand Arguments: {e}") from e
    else:
        expandend_params = {
            port.key: args.get(port.key, None) for port in definition.args
        }

    return expandend_params


async def ashrink_return(
    port: PortInput,
    value: Any,  # noqa: ANN401
    structure_registry: StructureRegistry,
    shelver: Shelver,
    *,
    path: Sequence[str] | None = None,
    depth: int = 0,
) -> JSONSerializable:
    """Shrink a value through a port

    This function is used to shrink a value to a smaller json serializable value
    with the help of the port definition and the structure registry, where potential
    shrinkers for funtions are registered.


    Args:
        port (ArgPort): Port to expand to
        value (Any): Value to expand
    Returns:
        Any: Expanded value

    """
    try:
        if value is None:
            if port.nullable:
                return None
            else:
                raise to_shrink_port_error(
                    port,
                    value,
                    f"Port {port.key} is not nullable (optional) but received None",
                    path=[*(path or []), port.key] if path is not None else [port.key],
                    depth=depth,
                )

        if port.kind == PortKind.UNION:
            if not port.children:
                raise to_shrink_port_error(
                    port,
                    value,
                    "Port is union but does not have children. Please report this to the developers.",
                    path=[*(path or []), port.key] if path is not None else [port.key],
                    depth=depth,
                )

            for index, possible_port in enumerate(port.children):
                if predicate_port_input(possible_port, value, structure_registry):
                    return {
                        "use": index,
                        "value": await ashrink_return(
                            possible_port,
                            value,
                            structure_registry=structure_registry,
                            shelver=shelver,
                            path=[*(path or []), f"{port.key}[{index}]"]
                            if path is not None
                            else [f"{port.key}[{index}]"],
                            depth=depth + 1,
                        ),
                    }

            raise to_shrink_port_error(
                port,
                value,
                f"Port is union but none of the predicates for this port held true. Children: {[c.key for c in port.children]}",
                path=[*(path or []), port.key] if path is not None else [port.key],
                depth=depth,
            )

        if port.kind == PortKind.DICT:
            if not port.children:
                raise to_shrink_port_error(
                    port,
                    value,
                    "Port is dict but does not have children. Please report this to the developers.",
                    path=[*(path or []), port.key] if path is not None else [port.key],
                    depth=depth,
                )

            if not isinstance(value, dict):
                raise to_shrink_port_error(
                    port,
                    value,
                    f"Port is dict but value is not a dict, got {type(value).__name__}",
                    path=[*(path or []), port.key] if path is not None else [port.key],
                    depth=depth,
                )

            if len(port.children) != 1:
                raise to_shrink_port_error(
                    port,
                    value,
                    f"Port is dict but has {len(port.children)} children (expected 1). Please report this to the developers.",
                    path=[*(path or []), port.key] if path is not None else [port.key],
                    depth=depth,
                )
            dict_port = port.children[0]

            return {
                key: await ashrink_return(
                    dict_port,
                    val,
                    structure_registry=structure_registry,
                    shelver=shelver,
                    path=[*(path or []), port.key, key]
                    if path is not None
                    else [port.key, key],
                    depth=depth + 1,
                )
                for key, val in value.items()
            }

        if port.kind == PortKind.LIST:
            if not isinstance(value, list):
                raise to_shrink_port_error(
                    port,
                    value,
                    f"Port is list but value is not a list, got {type(value).__name__}",
                    path=[*(path or []), port.key] if path is not None else [port.key],
                    depth=depth,
                )

            if not port.children:
                raise to_shrink_port_error(
                    port,
                    value,
                    "Port is list but does not have children. Please report this to the developers.",
                    path=[*(path or []), port.key] if path is not None else [port.key],
                    depth=depth,
                )

            if len(port.children) != 1:
                raise to_shrink_port_error(
                    port,
                    value,
                    f"Port is list but has {len(port.children)} children (expected 1). Please report this to the developers.",
                    path=[*(path or []), port.key] if path is not None else [port.key],
                    depth=depth,
                )

            return await asyncio.gather(
                *[
                    ashrink_return(
                        port.children[0],
                        item,
                        structure_registry=structure_registry,
                        shelver=shelver,
                        path=[*(path or []), f"{port.key}[{index}]"]
                        if path is not None
                        else [f"{port.key}[{index}]"],
                        depth=depth + 1,
                    )
                    for index, item in enumerate(cast(List[Any], value))
                ]
            )

        if port.kind == PortKind.MODEL:
            if not port.children:
                raise to_shrink_port_error(
                    port,
                    value,
                    "Port is model but does not have children. Please report this to the developers.",
                    path=[*(path or []), port.key] if path is not None else [port.key],
                    depth=depth,
                )
            if not port.identifier:
                raise to_shrink_port_error(
                    port,
                    value,
                    "Port is model but does not have identifier. Please report this to the developers.",
                    path=[*(path or []), port.key] if path is not None else [port.key],
                    depth=depth,
                )

            shrinked_args = await asyncio.gather(
                *[
                    ashrink_return(
                        child_port,
                        getattr(value, child_port.key),
                        structure_registry=structure_registry,
                        shelver=shelver,
                        path=[*(path or []), port.key, child_port.key]
                        if path is not None
                        else [port.key, child_port.key],
                        depth=depth + 1,
                    )
                    for child_port in port.children
                ]
            )

            shrinked_params = {
                child_port.key: val
                for child_port, val in zip(port.children, shrinked_args)
            }

            return shrinked_params

        if port.kind == PortKind.INT:
            if not isinstance(value, int):
                raise to_shrink_port_error(
                    port,
                    value,
                    f"Expected int, got {type(value).__name__}: {repr(value)}",
                    path=[*(path or []), port.key] if path is not None else [port.key],
                    depth=depth,
                )
            return int(value)

        if port.kind == PortKind.FLOAT:
            if not isinstance(value, (float, int)):
                raise to_shrink_port_error(
                    port,
                    value,
                    f"Expected float (or int), got {type(value).__name__}: {repr(value)}",
                    path=[*(path or []), port.key] if path is not None else [port.key],
                    depth=depth,
                )
            return float(value)

        if port.kind == PortKind.DATE:
            if not isinstance(value, dt.datetime):
                raise to_shrink_port_error(
                    port,
                    value,
                    f"Expected datetime, got {type(value).__name__}: {repr(value)}",
                    path=[*(path or []), port.key] if path is not None else [port.key],
                    depth=depth,
                )
            return value.isoformat()

        if port.kind == PortKind.MEMORY_STRUCTURE:
            if not port.identifier:
                raise to_shrink_port_error(
                    port,
                    value,
                    "Port is memory structure but does not have identifier. Please report this to the developers.",
                    path=[*(path or []), port.key] if path is not None else [port.key],
                    depth=depth,
                )

            return await shelver.aput_on_shelve(
                Identifier.validate(port.identifier), value
            )

        if port.kind == PortKind.STRUCTURE:
            if not port.identifier:
                raise to_shrink_port_error(
                    port,
                    value,
                    "Port is structure but does not have identifier. Please report this to the developers.",
                    path=[*(path or []), port.key] if path is not None else [port.key],
                    depth=depth,
                )
            fstruc = structure_registry.get_fullfilled_structure(port.identifier)
            try:
                shrink = await fstruc.ashrink(value)
                return str(shrink)
            except Exception as e:
                raise to_shrink_port_error(
                    port,
                    value,
                    f"Error shrinking with Structure {port.identifier}: {str(e)}",
                    path=[*(path or []), port.key] if path is not None else [port.key],
                    depth=depth,
                ) from e

        if port.kind == PortKind.BOOL:
            if isinstance(value, str):
                if value.lower() == "true":
                    return True
                elif value.lower() == "false":
                    return False
                else:
                    raise to_shrink_port_error(
                        port,
                        value,
                        f"Can't shrink string '{value}' to bool. We only accept 'true' or 'false'",
                        path=[*(path or []), port.key]
                        if path is not None
                        else [port.key],
                        depth=depth,
                    )
            if isinstance(value, int):
                if value == 1:
                    return True
                elif value == 0:
                    return False
                else:
                    raise to_shrink_port_error(
                        port,
                        value,
                        f"Can't shrink int {value} to bool. We only accept 0 or 1",
                        path=[*(path or []), port.key]
                        if path is not None
                        else [port.key],
                        depth=depth,
                    )

            if isinstance(value, bool):
                return value

            raise to_shrink_port_error(
                port,
                value,
                f"Expected bool, str, or int, got {type(value).__name__}: {repr(value)}",
                path=[*(path or []), port.key] if path is not None else [port.key],
                depth=depth,
            )

        if port.kind == PortKind.STRING:
            if not isinstance(value, str):
                raise to_shrink_port_error(
                    port,
                    value,
                    f"Expected str, got {type(value).__name__}: {repr(value)}",
                    path=[*(path or []), port.key] if path is not None else [port.key],
                    depth=depth,
                )
            return str(value)

        if port.kind == PortKind.ENUM:
            if not isinstance(value, Enum):
                raise to_shrink_port_error(
                    port,
                    value,
                    f"Expected Enum, got {type(value).__name__}: {repr(value)}",
                    path=[*(path or []), port.key] if path is not None else [port.key],
                    depth=depth,
                )
            return value.name

        raise to_shrink_port_error(
            port,
            value,
            f"Unsupported port kind: {port.kind}",
            path=[*(path or []), port.key] if path is not None else [port.key],
            depth=depth,
        )

    except ShrinkingError:
        raise
    except Exception as e:
        raise to_shrink_port_error(
            port,
            value,
            f"Unexpected error: {str(e)}",
            path=[*(path or []), port.key] if path is not None else [port.key],
            depth=depth,
        ) from e


async def shrink_outputs(
    definition: DefinitionInput,
    returns: List[Any] | None,
    structure_registry: StructureRegistry,
    shelver: Shelver,
    skip_shrinking: bool = False,
) -> Dict[str, JSONSerializable]:
    """Shrink the output of a function

    Args:
        definition (DefinitionInput): The function definition
        returns (List[Any]): The return values of the function
        structure_registry (StructureRegistry): The structure registry
        shelver (Shelver): The shelver
        skip_shrinking (bool): If True, skip shrinking

    Returns:
        Dict[str, Union[str, int, float, dict, list, None]]: The shrunk values
    """
    action = definition

    if returns is None:
        returns = []
    elif not isinstance(returns, tuple):
        returns = [returns]

    assert (
        len(action.returns) == len(returns)
    ), (  # We are dealing with a single output, convert it to a proper port like structure
        f"Mismatch in Return Length: expected {len(action.returns)} got {len(returns)}"
    )

    if not skip_shrinking:
        shrinked_returns_future = [
            ashrink_return(
                port,
                val,
                structure_registry,
                shelver=shelver,
                path=[port.key],
                depth=0,
            )
            for port, val in zip(action.returns, returns)
        ]
        shrinked_returns = await asyncio.gather(*shrinked_returns_future)
        return {port.key: val for port, val in zip(action.returns, shrinked_returns)}
    else:
        return {port.key: val for port, val in zip(action.returns, returns)}


async def ashrink_actor_arg(
    port: PortInput,
    value: Any,  # noqa: ANN401
    structure_registry: StructureRegistry,
) -> JSONSerializable:
    """Expand a value through a port

    Args:
        port (ArgPort): Port to expand to
        value (Any): Value to expand
    Returns:
        Any: Expanded value

    """
    try:
        if value is None:
            if port.nullable:
                return None
            else:
                raise ShrinkingError(
                    "{port} is not nullable (optional) but your provided None"
                )

        if port.kind == PortKind.DICT:
            if isinstance(port, ChildPortNestedChildren):
                raise ShrinkingError(
                    f"Maximum nesting level reached for {port} with value {value}"
                )

            if not isinstance(value, dict):
                raise ShrinkingError(
                    f"Expected value to be a dict, but got {type(value)}"
                )

            if not all(isinstance(k, str) for k in value.keys()):  # type: ignore
                raise ShrinkingError(
                    f"Expected all keys to be strings, but got {value.keys()}"
                )

            if not port.children:
                raise ShrinkingError(
                    f"Port {port} has no children, but value is a dict"
                )

            if len(port.children) != 1:
                raise ShrinkingError(
                    f"Port {port} has more than one child, but value is a dict"
                )

            child = port.children[0]

            return {
                key: await ashrink_actor_arg(
                    child,
                    value,
                    structure_registry=structure_registry,
                )
                for key, value in value.items()  # type: ignore
            }

        if port.kind == PortKind.LIST:
            if isinstance(port, ChildPortNestedChildren):
                raise ShrinkingError(
                    f"Maximum nesting level reached for {port} with value {value}"
                )

            if not isinstance(value, list):
                raise ShrinkingError(
                    f"Expected value to be a list, but got {type(value)}"
                )

            if not port.children:
                raise ShrinkingError(
                    f"Port {port} has no children, but value is a dict"
                )

            if len(port.children) != 1:
                raise ShrinkingError(
                    f"Port {port} has more than one child, but value is a dict"
                )

            child = port.children[0]

            return await asyncio.gather(
                *[
                    ashrink_actor_arg(
                        child,
                        item,
                        structure_registry=structure_registry,
                    )
                    for item in cast(List[Any], value)
                ]
            )

        if port.kind == PortKind.FLOAT:
            return float(value) if value is not None else None

        if port.kind == PortKind.INT:
            return int(value) if value is not None else None

        if port.kind == PortKind.UNION:
            if isinstance(port, ChildPortNestedChildren):
                raise ShrinkingError(
                    f"Maximum nesting level reached for {port} with value {value}"
                )

            if not port.children:
                raise ShrinkingError(
                    f"Port {port} has no children, but value is a dict"
                )

            for index, possible_port in enumerate(port.children):
                if predicate_serializable_port(
                    possible_port, value, structure_registry
                ):
                    return {
                        "use": index,
                        "value": await ashrink_actor_arg(
                            possible_port, value, structure_registry
                        ),
                    }

            raise ShrinkingError(
                f"Port is union butn none of the predicated for this port held true {port.children}"
            )

        if port.kind == PortKind.DATE:
            return value.isoformat() if value is not None else None

        if port.kind == PortKind.ENUM:
            if isinstance(port, ChildPortNestedChildren):
                raise ShrinkingError(
                    f"Maximum nesting level reached for {port} with value {value}"
                )

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

            is_in_choices = False
            for choice in port.choices:
                if value == choice.value:
                    is_in_choices = True
                    break

            if not is_in_choices:
                raise ShrinkingError(
                    f"Expected value to be in {port.choices}, but got {value}"
                )

            return value

        if port.kind == PortKind.MEMORY_STRUCTURE:
            if not isinstance(value, str):
                raise ShrinkingError(
                    f"Memory structures can always be just a reference to a memory drawer but got {type(value)}"
                )

            return value

        if port.kind == PortKind.STRUCTURE:
            if not port.identifier:
                raise ShrinkingError(
                    f"Port {port} is a structure but has no identifier"
                )

            if isinstance(value, str):
                # If the value is a string, we assume it's a reference to a global structure
                return value

            fenum = structure_registry.get_fullfilled_structure(port.identifier)

            try:
                shrink = await fenum.ashrink(value)
                return str(shrink)
            except Exception:
                raise StructureShrinkingError(
                    f"Error shrinking {repr(value)} with Structure {port.identifier}"
                ) from None

        if port.kind == PortKind.BOOL:
            return bool(value) if value is not None else None

        if port.kind == PortKind.STRING:
            return str(value) if value is not None else None

        if port.kind == PortKind.MODEL:
            if isinstance(port, ChildPortNestedChildren):
                raise ShrinkingError(
                    f"Maximum nesting level reached for {port} with value {value}"
                )

            if not port.identifier:
                raise ShrinkingError(f"Port {port} is a model but has no identifier")

            if not port.children:
                raise ShrinkingError(f"Port {port} is a model but has no children")

            try:
                shrinked_args = await asyncio.gather(
                    *[
                        ashrink_actor_arg(
                            port,
                            getattr(value, port.key),  # type: ignore
                            structure_registry=structure_registry,
                        )
                        for port in port.children
                    ]
                )

                if not port.children:
                    raise ShrinkingError(f"Port {port} has no children.")

                shrinked_params: dict[str, Any] = {
                    port.key: val for port, val in zip(port.children, shrinked_args)
                }

                return shrinked_params

            except Exception as e:
                raise PortShrinkingError(
                    f"Couldn't shrink Children {port.children}"
                ) from e

        raise NotImplementedError(f"Should be implemented by subclass {port}")

    except Exception as e:
        raise PortShrinkingError(
            f"Couldn't shrink value {value} with port {port}"
        ) from e


async def ashrink_actor_args(
    definition: DefinitionInput,
    args: Sequence[Any],
    kwargs: Dict[str, Any],
    structure_registry: StructureRegistry,
) -> Dict[str, JSONSerializable]:
    """Shrinks args and kwargs

    Shrinks the inputs according to the Action Definition

    Args:
        action (Action): The Action

    Raises:
        ShrinkingError: If args are not Shrinkable
        ShrinkingError: If kwargs are not Shrinkable

    Returns:
        Tuple[List[Any], Dict[str, Any]]: Parsed Args as a List, Parsed Kwargs as a dict
    """

    try:
        args_iterator = iter(args)
    except TypeError:
        raise ShrinkingError(f"Couldn't iterate over args {args}")

    # Extract to Argslist

    shrinked_kwargs: dict[str, JSONSerializable] = {}

    for port in definition.args:
        try:
            arg = next(args_iterator)
        except StopIteration as e:
            if port.key in kwargs:
                arg = kwargs[port.key]
            else:
                if port.nullable or port.default is not None:
                    arg = None  # defaults will be set by the agent
                else:
                    raise ShrinkingError(
                        f"Couldn't find value for nonnunllable port {port.key}"
                    ) from e

        try:
            shrunk_arg = await ashrink_actor_arg(
                port, arg, structure_registry=structure_registry
            )
            shrinked_kwargs[port.key] = shrunk_arg
        except Exception as e:
            raise ShrinkingError(f"Couldn't shrink arg {arg} with port {port}") from e

    return shrinked_kwargs


async def aexpand_actor_return(
    port: PortInput,
    value: JSONSerializable,  # noqa: ANN401
    structure_registry: StructureRegistry,
) -> Any:  # noqa: ANN401
    """Expand a value through a port

    Args:
        port (ArgPort): Port to expand to
        value (Any): Value to expand
    Returns:
        Any: Expanded value

    """
    if value is None:
        if port.nullable:
            return None
        else:
            raise PortExpandingError(
                f"{port.key} is not nullable (optional) but your provided None"
            )

    if port.kind == PortKind.DICT:
        if isinstance(port, ChildPortNestedChildren):
            raise PortExpandingError(
                f"Maximum recursion depth exceeded for port {port.identifier}"
            )

        if not isinstance(value, dict):
            raise PortExpandingError(
                f"Expected value to be a dict, but got {type(value)}"
            )

        if not port.children:
            raise PortExpandingError(f"Port {port.identifier} has no children")

        if len(port.children) != 1:
            raise PortExpandingError(f"Port {port.identifier} has more than one child")

        if isinstance(port, ChildPortNestedChildren):
            raise PortExpandingError(
                f"Maximum recursion depth exceeded for port {port.identifier}"
            )

        return {
            key: await aexpand_actor_return(
                port.children[0],
                value,
                structure_registry=structure_registry,
            )
            for key, value in value.items()
        }

    if port.kind == PortKind.LIST:
        if isinstance(port, ChildPortNestedChildren):
            raise PortExpandingError(
                f"Maximum recursion depth exceeded for port {port.identifier}"
            )

        if not isinstance(value, list):
            raise PortExpandingError(
                f"Expected value to be a list, but got {type(value)}"
            )

        if not port.children:
            raise PortExpandingError(f"Port {port.identifier} has no children")

        if len(port.children) != 1:
            raise PortExpandingError(f"Port {port.identifier} has more than one child")

        return await asyncio.gather(
            *[
                aexpand_actor_return(
                    port.children[0],
                    item,
                    structure_registry=structure_registry,
                )
                for item in value
            ]
        )

    if port.kind == PortKind.UNION:
        if isinstance(port, ChildPortNestedChildren):
            raise PortExpandingError(
                f"Maximum recursion depth exceeded for port {port.identifier}"
            )

        if not port.children:
            raise PortExpandingError(f"Port {port.identifier} has no children")

        if len(port.children) < 1:
            raise PortExpandingError(
                f"Port {port.identifier} has not more than one child"
            )

        assert isinstance(value, dict), "Union value needs to be a dict"
        assert "use" in value, "No use in vaalue"
        index = value["use"]
        true_value = value["value"]

        if not isinstance(index, int):
            raise PortExpandingError(
                f"Expected index to be an int, but got {type(index)}"
            )

        return await aexpand_actor_return(
            port.children[index],
            true_value,
            structure_registry=structure_registry,
        )

    if port.kind == PortKind.INT:
        if not isinstance(value, (int, str)):
            raise PortExpandingError(
                f"Expected value to be an int or str, but got {type(value)}"
            )
        return int(value)

    if port.kind == PortKind.FLOAT:
        if not isinstance(value, (float, str)):
            raise PortExpandingError(
                f"Expected value to be a float or str, but got {type(value)}"
            )
        return float(value)

    if port.kind == PortKind.DATE:
        if not isinstance(value, str):
            raise PortExpandingError(
                f"Expected value to be a string, but got {type(value)}"
            )
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))

    if port.kind == PortKind.MEMORY_STRUCTURE:
        if not isinstance(value, str):
            raise PortExpandingError(
                f"Expected value to be a string, but got {type(value)}"
            )

        return value

    if port.kind == PortKind.STRUCTURE:
        if not port.identifier:
            raise PortExpandingError(
                f"Port {port} is a structure but has no identifier"
            )
        if not (isinstance(value, str) or isinstance(value, int)):
            raise PortExpandingError(
                f"Expected value to be a string or int, but got {type(value)}"
            )

        try:
            fstruc = structure_registry.get_fullfilled_structure(port.identifier)
        except KeyError as e:
            raise PortExpandingError(
                f"Structure {port.identifier} not found. Was it ever registered?"
            ) from e

        try:
            return await fstruc.aexpand(ID.validate(value))
        except Exception:
            raise StructureExpandingError(
                f"Error expanding {repr(value)} with Structure {port.identifier}"
            ) from None

    if port.kind == PortKind.BOOL:
        return bool(value)

    if port.kind == PortKind.STRING:
        return str(value)

    raise StructureExpandingError(f"No valid expander found for {port.kind}")


async def aexpand_actor_returns(
    definition: DefinitionInput,
    returns: Dict[str, JSONSerializable],
    structure_registry: StructureRegistry,
) -> Tuple[Any]:
    """Expands Returns

    Expands the Returns according to the Action definition


    Args:
        action (Action): Action definition
        returns (List[any]): The returns

    Raises:
        ExpandingError: if they are not expandable

    Returns:
        List[Any]: The Expanded Returns
    """
    assert returns is not None, "Returns can't be empty"

    expanded_returns: list[Any] = []

    for port in definition.returns:
        expanded_return = None
        if port.key not in returns:
            if port.nullable:
                returns[port.key] = None
            else:
                raise ExpandingError(f"Missing key {port.key} in returns")

        else:
            try:
                expanded_return = await aexpand_actor_return(
                    port,
                    returns[port.key],
                    structure_registry=structure_registry,
                )
            except Exception as e:
                raise ExpandingError(
                    f"Couldn't expand the reutrn value `{returns[port.key]}` for port {port.key}"
                ) from e

        expanded_returns.append(expanded_return)

    return tuple(expanded_returns)
