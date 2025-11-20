"""Serialization for Postman"""

from enum import Enum
from typing import Any, Dict, List, Sequence, Tuple, cast

from rekuest_next.api.schema import Action, ChildPortNestedChildren
import asyncio
from rekuest_next.structures.errors import ExpandingError, ShrinkingError
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.api.schema import (
    PortKind,
)
from rath.scalars import ID
from rekuest_next.structures.errors import (
    PortShrinkingError,
    StructureShrinkingError,
    PortExpandingError,
    StructureExpandingError,
)
from rekuest_next.structures.serialization.protocols import SerializablePort
from rekuest_next.structures.types import JSONSerializable
from .predication import predicate_serializable_port
import datetime as dt


async def ashrink_arg(
    port: SerializablePort,
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
                key: await ashrink_arg(
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
                    ashrink_arg(
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
                        "value": await ashrink_arg(
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
                        ashrink_arg(
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


async def ashrink_args(
    action: Action,
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

    for port in action.args:
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
            shrunk_arg = await ashrink_arg(
                port, arg, structure_registry=structure_registry
            )
            shrinked_kwargs[port.key] = shrunk_arg
        except Exception as e:
            raise ShrinkingError(f"Couldn't shrink arg {arg} with port {port}") from e

    return shrinked_kwargs


async def aexpand_return(
    port: SerializablePort,
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
                f"{port} is not nullable (optional) but your provided None"
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
            key: await aexpand_return(
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
                aexpand_return(
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

        return await aexpand_return(
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


async def aexpand_returns(
    action: Action,
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

    for port in action.returns:
        expanded_return = None
        if port.key not in returns:
            if port.nullable:
                returns[port.key] = None
            else:
                raise ExpandingError(f"Missing key {port.key} in returns")

        else:
            try:
                expanded_return = await aexpand_return(
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
