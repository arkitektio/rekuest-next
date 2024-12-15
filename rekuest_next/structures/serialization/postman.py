from typing import Any, Dict, List, Tuple, Union
from rekuest_next.api.schema import Node
import asyncio
from rekuest_next.structures.errors import ExpandingError, ShrinkingError
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.api.schema import (
    Port,
    PortKind,
    DefinitionInput,
    Definition,
    ChildPort,
)
from rekuest_next.structures.errors import (
    PortShrinkingError,
    StructureShrinkingError,
    PortExpandingError,
    StructureExpandingError,
)
from .predication import predicate_port
import datetime as dt


async def ashrink_arg(
    port: Union[Port, ChildPort], value: Any, structure_registry=None
) -> Any:
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
                raise ValueError(
                    "{port} is not nullable (optional) but your provided None"
                )

        if port.kind == PortKind.DICT:
            return {
                key: await ashrink_arg(port.children[0], value, structure_registry)
                for key, value in value.items()
            }

        if port.kind == PortKind.LIST:
            return await asyncio.gather(
                *[
                    ashrink_arg(
                        port.children[0], item, structure_registry=structure_registry
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
                        "value": await ashrink_arg(x, value, structure_registry),
                    }

            raise ShrinkingError(
                f"Port is union butn none of the predicated for this port held true {port.children}"
            )

        if port.kind == PortKind.DATE:
            return value.isoformat() if value is not None else None

        if port.kind == PortKind.STRUCTURE:
            # We always convert structures returns to strings
            try:
                shrinker = structure_registry.get_shrinker_for_identifier(
                    port.identifier
                )
            except KeyError:
                raise StructureShrinkingError(
                    f"Couldn't find shrinker for {port.identifier}"
                ) from None
            try:
                shrink = await shrinker(value)
                return str(shrink)
            except Exception:
                raise StructureShrinkingError(
                    f"Error shrinking {repr(value)} with Structure {port.identifier}"
                ) from None

        if port.kind == PortKind.BOOL:
            return bool(value) if value is not None else None

        if port.kind == PortKind.STRING:
            return str(value) if value is not None else None

        raise NotImplementedError(f"Should be implemented by subclass {port}")

    except Exception as e:
        raise PortShrinkingError(
            f"Couldn't shrink value {value} with port {port}"
        ) from e


async def ashrink_args(
    node: Node,
    args: List[Any],
    kwargs: Dict[str, Any],
    structure_registry: StructureRegistry,
) -> Dict[str, Any]:
    """Shrinks args and kwargs

    Shrinks the inputs according to the Node Definition

    Args:
        node (Node): The Node

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

    for port in node.args:
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
            shrunk_arg = await ashrink_arg(port, arg, structure_registry)
            shrinked_kwargs[port.key] = shrunk_arg
        except Exception as e:
            raise ShrinkingError(f"Couldn't shrink arg {arg} with port {port}") from e

    return shrinked_kwargs


async def aexpand_return(
    port: Union[Port, ChildPort],
    value: Any,
    structure_registry=None,
) -> Any:
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
        return {
            key: await aexpand_return(port.child, value, structure_registry)
            for key, value in value.items()
        }

    if port.kind == PortKind.LIST:
        return await asyncio.gather(
            *[
                aexpand_return(port.child, item, structure_registry=structure_registry)
                for item in value
            ]
        )

    if port.kind == PortKind.UNION:
        assert isinstance(value, dict), "Union value needs to be a dict"
        assert "use" in value, "No use in vaalue"
        index = value["use"]
        true_value = value["value"]
        return await aexpand_return(
            port.variants[index], true_value, structure_registry=structure_registry
        )

    if port.kind == PortKind.INT:
        return int(value)

    if port.kind == PortKind.FLOAT:
        return float(value)

    if port.kind == PortKind.DATE:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))

    if port.kind == PortKind.STRUCTURE:
        if not (isinstance(value, str) or isinstance(value, int)):
            raise PortExpandingError(
                f"Expected value to be a string or int, but got {type(value)}"
            )

        try:
            expander = structure_registry.get_expander_for_identifier(port.identifier)
        except KeyError:
            raise StructureExpandingError(
                f"Couldn't find expander for {port.identifier}"
            ) from None

        try:
            return await expander(value)
        except Exception:
            raise StructureExpandingError(
                f"Error expanding {repr(value)} with Structure {port.identifier}"
            ) from None

    if port.kind == PortKind.BOOL:
        return bool(value)

    if port.kind == PortKind.STRING:
        return str(value)

    raise NotImplementedError("Should be implemented by subclass")


async def aexpand_returns(
    node: Node,
    returns: Dict[str, Any],
    structure_registry: StructureRegistry,
) -> Tuple[Any]:
    """Expands Returns

    Expands the Returns according to the Node definition


    Args:
        node (Node): Node definition
        returns (List[any]): The returns

    Raises:
        ExpandingError: if they are not expandable

    Returns:
        List[Any]: The Expanded Returns
    """
    assert returns is not None, "Returns can't be empty"

    expanded_returns = []

    for port in node.returns:
        expanded_return = None
        if port.key not in returns:
            if port.nullable:
                returns[port.key] = None
            else:
                raise ExpandingError(f"Missing key {port.key} in returns")

        else:
            try:
                expanded_return = await aexpand_return(
                    port, returns[port.key], structure_registry
                )
            except Exception as e:
                raise ExpandingError(
                    f"Couldn't expand return {returns[port.key]} with port {port}"
                ) from e

        expanded_returns.append(expanded_return)

    return expanded_return


def serialize_inputs(
    definition: Union[Definition, DefinitionInput],
    kwargs: Dict[str, Any],
) -> Tuple[Any]:
    """Shrinks args and kwargs

    Shrinks the inputs according to the Node Definition

    Args:
        node (Node): The Node

    Raises:
        ShrinkingError: If args are not Shrinkable
        ShrinkingError: If kwargs are not Shrinkable

    Returns:
        Tuple[List[Any], Dict[str, Any]]: Parsed Args as a List, Parsed Kwargs as a dict
    """

    args_list = []

    # Extract to Argslist

    for port in definition.args:
        value = kwargs.pop(port.key, None)
        if value is None and not port.nullable:
            raise ShrinkingError(
                f"Couldn't find value for nonnunllable port {port.key}"
            )
        args_list.append(value)

    shrinked_args = args_list

    return tuple(shrinked_args)


def deserialize_outputs(
    definition: Union[Definition, DefinitionInput],
    returns: List[Any],
) -> Dict[str, Any]:
    """Expands Returns

    Expands the Returns according to the Node definition


    Args:
        node (Node): Node definition
        returns (List[any]): The returns

    Raises:
        ExpandingError: if they are not expandable

    Returns:
        Dcit[str, Any]: The Expanded Returns
    """
    assert returns is not None, "Returns can't be empty"
    if len(definition.returns) != len(returns):
        raise ExpandingError(
            f"Missmatch in Return Length. Node requires {len(definition.returns)} returns,"
            f" but got {len(returns)}"
        )

    values = {}

    for port, value in zip(definition.returns, returns):
        values[port.key] = value

    return values
