from typing import Any, Dict, List
import asyncio
from rekuest_next.structures.errors import ExpandingError, ShrinkingError
from rekuest_next.structures.registry import StructureRegistry
from typing import Union
from rekuest_next.api.schema import (
    Port,
    PortKind,
    ChildPort,
    DefinitionInput,
    Definition,
)
from rekuest_next.structures.errors import (
    PortShrinkingError,
    StructureShrinkingError,
    StructureExpandingError,
)
from rekuest_next.definition.validate import auto_validate
from .predication import predicate_port
import datetime as dt


async def aexpand_arg(
    port: Union[Port, ChildPort],
    value: Union[str, int, float, dict, list],
    structure_registry,
) -> Any:
    """Expand a value through a port

    Args:
        port (ArgPort): Port to expand to
        value (Any): Value to expand
    Returns:
        Any: Expanded value

    """
    if value is None:
        value = port.default

    if value is None:
        if port.nullable:
            return None
        else:
            raise ExpandingError(
                f"{port.key} is not nullable (optional) but received None"
            )

    if not isinstance(value, (str, int, float, dict, list)):
        raise ExpandingError(
            f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
            " strings, ints and floats (json serializable) and null values"
        ) from None

    if port.kind == PortKind.DICT:
        expanding_port = port.children[0]

        if not isinstance(value, dict):
            raise ExpandingError(
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only"
                " accept dicts"
            ) from None

        return {
            key: await aexpand_arg(expanding_port, value, structure_registry)
            for key, value in value.items()
        }

    if port.kind == PortKind.UNION:
        if not isinstance(value, dict):
            raise ExpandingError(
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only"
                " accept dicts in unions"
            )
        assert "use" in value, "No use in vaalue"
        index = value["use"]
        true_value = value["value"]
        return await aexpand_arg(
            port.children[index], true_value, structure_registry=structure_registry
        )

    if port.kind == PortKind.LIST:
        expanding_port = port.children[0]

        if not isinstance(value, list):
            raise ExpandingError(
                f"Can't expand {value} of type {type(value)} to {port.kind}. Only"
                " accept lists"
            ) from None

        return await asyncio.gather(
            *[aexpand_arg(expanding_port, item, structure_registry) for item in value]
        )

    if port.kind == PortKind.MODEL:
        try:
            expanded_args = await asyncio.gather(
                *[
                    aexpand_arg(port, value[port.key], structure_registry)
                    for port in port.children
                ]
            )

            expandend_params = {
                port.key: val for port, val in zip(port.children, expanded_args)
            }

            expander = structure_registry.retrieve_model_expander(port.identifier)
            expanded_values = await expander(expandend_params)
            return expanded_values

        except Exception as e:
            raise ExpandingError(f"Couldn't expand Children {port.children}") from e

    if port.kind == PortKind.INT:
        return int(value)

    if port.kind == PortKind.DATE:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))

    if port.kind == PortKind.FLOAT:
        return float(value)

    if port.kind == PortKind.STRUCTURE:
        try:
            expander = structure_registry.get_expander_for_identifier(port.identifier)
        except KeyError:
            raise StructureExpandingError(
                f"Couldn't find expander for {port.identifier}"
            ) from None

        try:
            expand = await expander(value)
            return expand
        except Exception as e:
            raise StructureExpandingError(
                f"Error expanding {repr(value)} with Structure {port.identifier}"
            ) from e

    if port.kind == PortKind.BOOL:
        return bool(value)

    if port.kind == PortKind.STRING:
        return str(value)

    raise NotImplementedError("Should be implemented by subclass")


async def expand_inputs(
    definition: Union[DefinitionInput, Definition],
    args: Dict[str, Union[str, int, float, dict, list]],
    structure_registry: StructureRegistry,
    skip_expanding: bool = False,
):
    """Expand

    Args:
        node (Node): [description]
        args (List[Any]): [description]
        kwargs (List[Any]): [description]
        registry (Registry): [description]
    """

    expanded_args = []
    node = (
        auto_validate(definition)
        if isinstance(definition, DefinitionInput)
        else definition
    )

    if not skip_expanding:
        try:
            expanded_args = await asyncio.gather(
                *[
                    aexpand_arg(port, args.get(port.key, None), structure_registry)
                    for port in node.args
                ]
            )

            expandend_params = {
                port.key: val for port, val in zip(node.args, expanded_args)
            }

        except Exception as e:
            raise ExpandingError(f"Couldn't expand Arguments {args}: {e}") from e
    else:
        expandend_params = {port.key: args.get(port.key, None) for port in node.args}

    return expandend_params


async def ashrink_return(
    port: Union[Port, ChildPort],
    value: Any,
    structure_registry=None,
    assert_type: bool = True,
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
                raise ValueError(
                    f"{port} is not nullable (optional) but your provided None"
                )

        if port.kind == PortKind.UNION:
            for index, x in enumerate(port.children[0]):
                if predicate_port(x, value, structure_registry):
                    return {
                        "use": index,
                        "value": await ashrink_return(x, value, structure_registry),
                    }

            raise ShrinkingError(
                f"Port is union butn none of the predicated for this port held true {port.children}"
            )

        if port.kind == PortKind.DICT:
            assert isinstance(value, dict), f"Expected dict got {value}"
            return {
                key: await ashrink_return(port.children[0], value, structure_registry)
                for key, value in value.items()
            }

        if port.kind == PortKind.LIST:
            assert isinstance(value, list), f"Expected list got {value}"
            return await asyncio.gather(
                *[
                    ashrink_return(
                        port.children[0], item, structure_registry=structure_registry
                    )
                    for item in value
                ]
            )

        if port.kind == PortKind.MODEL:
            try:
                shrinked_args = await asyncio.gather(
                    *[
                        ashrink_return(
                            port, getattr(value, port.key), structure_registry
                        )
                        for port in port.children
                    ]
                )

                shrinked_params = {
                    port.key: val for port, val in zip(port.children, shrinked_args)
                }

                return shrinked_params

            except Exception as e:
                raise PortShrinkingError(
                    f"Couldn't shrink Children {port.children}"
                ) from e

        if port.kind == PortKind.INT:
            assert isinstance(value, int), f"Expected int got {value}"
            return int(value) if value is not None else None

        if port.kind == PortKind.FLOAT:
            assert isinstance(value, float) or isinstance(value, int), f"Expected float (or int) got {value}"
            return float(value) if value is not None else None

        if port.kind == PortKind.DATE:
            assert isinstance(value, dt.datetime), f"Expected date got {value}"
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
            except Exception as e:
                raise StructureShrinkingError(
                    f"Error shrinking {repr(value)} with Structure {port.identifier}"
                ) from e

        if port.kind == PortKind.BOOL:
            assert isinstance(value, bool), f"Expected bool got {value}"
            return bool(value) if value is not None else None

        if port.kind == PortKind.STRING:
            assert isinstance(value, str), f"Expected str got {value}"
            return str(value) if value is not None else None

        raise NotImplementedError(f"Should be implemented by subclass {port}")

    except Exception as e:
        raise PortShrinkingError(
            f"Couldn't shrink value {value} with port {port}"
        ) from e


async def shrink_outputs(
    definition: Union[DefinitionInput, Definition],
    returns: List[Any],
    structure_registry: StructureRegistry,
    skip_shrinking: bool = False,
) -> Dict[str, Union[str, int, float, dict, list, None]]:
    node = (
        auto_validate(definition)
        if isinstance(definition, DefinitionInput)
        else definition
    )

    if returns is None:
        returns = []
    elif not isinstance(returns, tuple):
        returns = [returns]

    assert len(node.returns) == len(
        returns
    ), (  # We are dealing with a single output, convert it to a proper port like structure
        f"Mismatch in Return Length: expected {len(node.returns)} got {len(returns)}"
    )

    if not skip_shrinking:
        shrinked_returns_future = [
            ashrink_return(port, val, structure_registry)
            for port, val in zip(node.returns, returns)
        ]
        try:
            shrinked_returns = await asyncio.gather(*shrinked_returns_future)
            return {port.key: val for port, val in zip(node.returns, shrinked_returns)}
        except Exception as e:
            raise ShrinkingError(f"Couldn't shrink Returns {returns}: {str(e)}") from e
    else:
        return {port.key: val for port, val in zip(node.returns, returns)}
