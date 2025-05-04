"""Serialization for Postman"""

from typing import Any, Dict, List, Tuple, Union
from rekuest_next.api.schema import Action
import asyncio
from rekuest_next.structures.errors import ExpandingError, ShrinkingError
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.api.schema import (
    Port,
    PortKind,
    ChildPort,
)
from rekuest_next.structures.errors import (
    PortShrinkingError,
    StructureShrinkingError,
    PortExpandingError,
    StructureExpandingError,
)
from rekuest_next.actors.types import Shelver
from .predication import predicate_port
import datetime as dt


async def ashrink_arg(
    port: Union[Port, ChildPort],
    value: Union[str, int, float, dict, list, None, Any],  # noqa: ANN401
    structure_registry: StructureRegistry,
    shelver: Shelver,
) -> Union[str, int, float, dict, list, None]:
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
                raise ValueError("{port} is not nullable (optional) but your provided None")

        if port.kind == PortKind.DICT:
            return {
                key: await ashrink_arg(
                    port.children[0],
                    value,
                    structure_registry=structure_registry,
                    shelver=shelver,
                )
                for key, value in value.items()
            }

        if port.kind == PortKind.LIST:
            return await asyncio.gather(
                *[
                    ashrink_arg(
                        port.children[0],
                        item,
                        structure_registry=structure_registry,
                        shelver=shelver,
                    )
                    for item in value
                ]
            )

        if port.kind == PortKind.INT:
            return int(value) if value is not None else None

        if port.kind == PortKind.UNION:
            for index, x in enumerate(port.children):
                if predicate_port(x, value, structure_registry):
                    return {
                        "use": index,
                        "value": await ashrink_arg(x, value, structure_registry, shelver=shelver),
                    }

            raise ShrinkingError(
                f"Port is union butn none of the predicated for this port held true {port.children}"
            )

        if port.kind == PortKind.DATE:
            return value.isoformat() if value is not None else None

        if port.kind == PortKind.ENUM:
            fenum = structure_registry.get_fullfilled_enum(port.identifier)
            return value.name

        if port.kind == PortKind.MEMORY_STRUCTURE:
            return await shelver.aput_on_shelve(value)

        if port.kind == PortKind.STRUCTURE:
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
            try:
                shrinked_args = await asyncio.gather(
                    *[
                        ashrink_arg(
                            port,
                            getattr(value, port.key),
                            structure_registry=structure_registry,
                            shelver=shelver,
                        )
                        for port in port.children
                    ]
                )

                shrinked_params = {port.key: val for port, val in zip(port.children, shrinked_args)}

                return shrinked_params

            except Exception as e:
                raise PortShrinkingError(f"Couldn't shrink Children {port.children}") from e

        raise NotImplementedError(f"Should be implemented by subclass {port}")

    except Exception as e:
        raise PortShrinkingError(f"Couldn't shrink value {value} with port {port}") from e


async def ashrink_args(
    action: Action,
    args: List[Any],
    kwargs: Dict[str, Any],
    structure_registry: StructureRegistry,
    shelver: Shelver,
) -> Dict[str, Union[str, int, float, dict, list, None]]:
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

    shrinked_kwargs = {}

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
                port, arg, structure_registry=structure_registry, shelver=shelver
            )
            shrinked_kwargs[port.key] = shrunk_arg
        except Exception as e:
            raise ShrinkingError(f"Couldn't shrink arg {arg} with port {port}") from e

    return shrinked_kwargs


async def aexpand_return(
    port: Union[Port, ChildPort],
    value: Union[str, int, float, dict, list, None],
    structure_registry: StructureRegistry,
    shelver: Shelver,
) -> Union[str, int, float, dict, list, None, Any]:  # noqa: ANN401
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
            raise PortExpandingError(f"{port} is not nullable (optional) but your provided None")

    if port.kind == PortKind.DICT:
        return {
            key: await aexpand_return(
                port.children[0],
                value,
                structure_registry=structure_registry,
                shelver=shelver,
            )
            for key, value in value.items()
        }

    if port.kind == PortKind.LIST:
        return await asyncio.gather(
            *[
                aexpand_return(
                    port.children[0],
                    item,
                    structure_registry=structure_registry,
                    shelver=shelver,
                )
                for item in value
            ]
        )

    if port.kind == PortKind.UNION:
        assert isinstance(value, dict), "Union value needs to be a dict"
        assert "use" in value, "No use in vaalue"
        index = value["use"]
        true_value = value["value"]
        return await aexpand_return(
            port.children[index],
            true_value,
            structure_registry=structure_registry,
            shelver=shelver,
        )

    if port.kind == PortKind.INT:
        return int(value)

    if port.kind == PortKind.FLOAT:
        return float(value)

    if port.kind == PortKind.DATE:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))

    if port.kind == PortKind.MEMORY_STRUCTURE:
        if not isinstance(value, str):
            raise PortExpandingError(f"Expected value to be a string, but got {type(value)}")

        try:
            return await shelver.aget_from_shelve(value)
        except Exception as e:
            raise PortExpandingError(f"Couldn't get value from shelve {value}") from e

    if port.kind == PortKind.STRUCTURE:
        if not (isinstance(value, str) or isinstance(value, int)):
            raise PortExpandingError(f"Expected value to be a string or int, but got {type(value)}")

        fstruc = structure_registry.get_fullfilled_structure(port.identifier)

        try:
            return await fstruc.aexpand(value)
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
    returns: Dict[str, Union[str, int, float, dict, list, None]],
    structure_registry: StructureRegistry,
    shelver: Shelver,
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

    expanded_returns = []

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
                    shelver=shelver,
                )
            except Exception as e:
                raise ExpandingError(
                    f"Couldn't expand return {returns[port.key]} with port {port}"
                ) from e

        expanded_returns.append(expanded_return)

    return expanded_return
