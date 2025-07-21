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


async def aexpand_arg(
    port: PortInput,
    value: JSONSerializable,
    structure_registry: StructureRegistry,
    shelver: Shelver,
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

    if value is None:
        if port.nullable:
            return None
        else:
            raise ExpandingError(f"{port.key} is not nullable (optional) but received None")

    if not isinstance(value, (str, int, float, dict, list)):  # type: ignore
        raise ExpandingError(
            f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
            " strings, ints and floats (json serializable) and null values"
        ) from None

    if port.kind == PortKind.DICT:
        if not port.children:
            raise ExpandingError(
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                " dicts with children"
            ) from None

        expanding_port = port.children[0]

        if not isinstance(value, dict):
            raise ExpandingError(
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept dicts"
            ) from None

        return {
            key: await aexpand_arg(
                expanding_port,
                value,
                structure_registry=structure_registry,
                shelver=shelver,
            )
            for key, value in value.items()
        }

    if port.kind == PortKind.UNION:
        if not port.children:
            raise ExpandingError(
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                " unions with children"
            ) from None

        if not isinstance(value, dict):
            raise ExpandingError(
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only"
                " accept dicts in unions"
            )
        assert "use" in value, "No use in vaalue"
        index = value["use"]
        true_value = value["value"]

        if isinstance(index, str):
            index = int(index)

        if not isinstance(index, int):
            raise ExpandingError(
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                " ints in unions"
            ) from None
        try:
            child = port.children[index]
        except IndexError as e:
            raise ExpandingError(
                f"Can't expand {value} of type {type(value)} to {port.kind}. The index {index} is"
                " out of range"
            ) from e

        return await aexpand_arg(
            child,
            true_value,
            structure_registry=structure_registry,
            shelver=shelver,
        )

    if port.kind == PortKind.LIST:
        if not port.children:
            raise ExpandingError(
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                " lists with children"
            ) from None

        expanding_port = port.children[0]

        if not isinstance(value, list):
            raise ExpandingError(
                f"Can't expand {value} of type {type(value)} to {port.kind}. Only accept lists"
            ) from None

        return await asyncio.gather(
            *[
                aexpand_arg(
                    expanding_port,
                    item,
                    structure_registry=structure_registry,
                    shelver=shelver,
                )
                for item in value
            ]
        )

    if port.kind == PortKind.MODEL:
        try:
            if not isinstance(value, dict):
                raise ExpandingError(
                    f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                    " dicts in models"
                )
            if not port.children:
                raise ExpandingError(
                    f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                    " models with children"
                )
            if not port.identifier:
                raise ExpandingError(
                    f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                    " models with identifiers"
                )

            expanded_args = await asyncio.gather(
                *[
                    aexpand_arg(
                        port,
                        value[port.key],
                        structure_registry=structure_registry,
                        shelver=shelver,
                    )
                    for port in port.children
                ]
            )

            # Redo the check for children and identifier because to satisfy mypy
            if not port.children:
                raise ExpandingError(
                    f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                    " models with children"
                )

            expandend_params = {port.key: val for port, val in zip(port.children, expanded_args)}

            if not port.identifier:
                raise ExpandingError(
                    f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                    " models with identifiers"
                )

            fmodel = structure_registry.get_fullfilled_model(port.identifier)
            return fmodel.cls(**expandend_params)

        except Exception as e:
            raise ExpandingError(f"Couldn't expand Children {port.children}") from e

    if port.kind == PortKind.INT:
        if not isinstance(value, (int, float, str)):
            raise ExpandingError(
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                " ints, floats and strings"
            ) from None
        return int(value)

    if port.kind == PortKind.DATE:
        if not isinstance(value, (str, dt.datetime)):
            raise ExpandingError(
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                " strings and datetime"
            ) from None
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))

    if port.kind == PortKind.FLOAT:
        if not isinstance(value, (int, float, str)):
            raise ExpandingError(
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                " ints, floats and strings"
            ) from None
        return float(value)

    if port.kind == PortKind.ENUM:
        if port.identifier is None:
            raise ExpandingError(
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                " enums with identifiers"
            ) from None

        fenum = structure_registry.get_fullfilled_enum(port.identifier)
        if fenum:
            if isinstance(value, str):
                if value not in fenum.cls.__members__:
                    raise ExpandingError(f"Enum {port.identifier} does not have {value} as member")
                return fenum.cls[value]
            if isinstance(value, int):
                if value not in fenum.cls.__members__.values():
                    raise ExpandingError(f"Enum {port.identifier} does not have {value} as member")
                return fenum.cls(value)
            else:
                raise ExpandingError(
                    f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                    " strings and ints"
                ) from None

        else:
            raise ExpandingError(f"Enum {port.identifier} not found in registry")

    if port.kind == PortKind.MEMORY_STRUCTURE:
        if not isinstance(value, (str, int)):
            raise ExpandingError(
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                " strings and ints"
            ) from None

        if isinstance(value, int):
            value = str(value)

        return await shelver.aget_from_shelve(value)

    if port.kind == PortKind.STRUCTURE:
        if not isinstance(value, (str, int)):
            raise ExpandingError(
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                " strings and ints"
            ) from None

        if isinstance(value, int):
            value = str(value)

        if not port.identifier:
            raise ExpandingError(
                f"Can't expand {value} of type {type(value)} to {port.kind}. We only accept"
                " structures with identifiers"
            ) from None

        fstruc = structure_registry.get_fullfilled_structure(port.identifier)

        try:
            expanded = await fstruc.aexpand(ID.validate(value))
            return expanded
        except Exception as e:
            raise StructureExpandingError(
                f"Error expanding {repr(value)} with Structure {port.identifier}"
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
                        args.get(port.key, None),
                        structure_registry=structure_registry,
                        shelver=shelver,
                    )
                    for port in definition.args
                ]
            )

            expandend_params = {port.key: val for port, val in zip(definition.args, expanded_args)}

        except Exception as e:
            raise ExpandingError(f"Couldn't expand Arguments {args}: {e}") from e
    else:
        expandend_params = {port.key: args.get(port.key, None) for port in definition.args}

    return expandend_params


async def ashrink_return(
    port: PortInput,
    value: Any,  # noqa: ANN401
    structure_registry: StructureRegistry,
    shelver: Shelver,
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
                raise ValueError(f"{port} is not nullable (optional) but your provided None")

        if port.kind == PortKind.UNION:
            if not port.children:
                raise ShrinkingError(f"Port is union but does not have children {port.children}")

            for index, possible_port in enumerate(port.children):
                if predicate_port_input(possible_port, value, structure_registry):
                    return {
                        "use": index,
                        "value": await ashrink_return(
                            possible_port,
                            value,
                            structure_registry=structure_registry,
                            shelver=shelver,
                        ),
                    }

            raise ShrinkingError(
                f"Port is union butn none of the predicated for this port held true {port.children}"
            )

        if port.kind == PortKind.DICT:
            if not port.children:
                raise ShrinkingError(f"Port is dict but does not have children {port.children}")

            if not isinstance(value, dict):
                raise ShrinkingError(f"Port is dict but value is not a dict {port.children}")

            if len(port.children) != 1:
                raise ShrinkingError(f"Port is dict but has more than one child {port.children}")
            dict_port = port.children[0]

            assert isinstance(value, dict), f"Expected dict got {value}"
            return {
                key: await ashrink_return(
                    dict_port,
                    value,
                    structure_registry=structure_registry,
                    shelver=shelver,
                )
                for key, value in value.items()  # type: ignore
            }

        if port.kind == PortKind.LIST:
            assert isinstance(value, list), f"Expected list got {value}"

            if not port.children:
                raise ShrinkingError(f"Port is list but does not have children {port.children}")

            if len(port.children) != 1:
                raise ShrinkingError(f"Port is list but has more than one child {port.children}")

            return await asyncio.gather(
                *[
                    ashrink_return(
                        port.children[0],
                        item,
                        structure_registry=structure_registry,
                        shelver=shelver,
                    )
                    for item in cast(List[Any], value)
                ]
            )

        if port.kind == PortKind.MODEL:
            if not port.children:
                raise ShrinkingError(f"Port is model but does not have children {port.children}")
            if not port.identifier:
                raise ShrinkingError(
                    f"Port is model but does not have identifier {port.identifier}"
                )

            try:
                shrinked_args = await asyncio.gather(
                    *[
                        ashrink_return(
                            port,
                            getattr(value, port.key),
                            structure_registry=structure_registry,
                            shelver=shelver,
                        )
                        for port in port.children
                    ]
                )

                if not port.children:
                    raise ShrinkingError(
                        f"Port is model but does not have children {port.children}"
                    )

                shrinked_params = {port.key: val for port, val in zip(port.children, shrinked_args)}

                return shrinked_params

            except Exception as e:
                raise PortShrinkingError(f"Couldn't shrink Children {port.children}") from e

        if port.kind == PortKind.INT:
            assert isinstance(value, int), f"Expected int got {value}"
            return int(value)

        if port.kind == PortKind.FLOAT:
            assert isinstance(value, float) or isinstance(value, int), (
                f"Expected float (or int) got {value}"
            )
            return float(value)

        if port.kind == PortKind.DATE:
            assert isinstance(value, dt.datetime), f"Expected date got {value}"
            return value.isoformat()

        if port.kind == PortKind.MEMORY_STRUCTURE:
            if not port.identifier:
                raise ShrinkingError(
                    f"Port is memory structure but does not have identifier {port.identifier}"
                )

            return await shelver.aput_on_shelve(Identifier.validate(port.identifier), value)

        if port.kind == PortKind.STRUCTURE:
            if not port.identifier:
                raise ShrinkingError(
                    f"Port is structure but does not have identifier {port.identifier}"
                )
            fstruc = structure_registry.get_fullfilled_structure(port.identifier)
            try:
                shrink = await fstruc.ashrink(value)
                return str(shrink)
            except Exception as e:
                raise StructureShrinkingError(
                    f"Error shrinking {repr(value)} with Structure {port.identifier}"
                ) from e

        if port.kind == PortKind.BOOL:
            if isinstance(value, str):
                if value.lower() == "true":
                    return True
                elif value.lower() == "false":
                    return False
                else:
                    raise ShrinkingError(
                        f"Can't shrink {value} of type {type(value)} to {port.kind}. We only accept"
                        " strings with true or false"
                    ) from None
            if isinstance(value, int):
                if value == 1:
                    return True
                elif value == 0:
                    return False
                else:
                    raise ShrinkingError(
                        f"Can't shrink {value} of type {type(value)} to {port.kind}. We only accept"
                        " ints with 0 or 1"
                    ) from None

            if isinstance(value, bool):
                return value

            raise ShrinkingError(
                f"Can't shrink {value} of type {type(value)} to {port.kind}. We only accept"
                " strings, ints and bools"
            ) from None

        if port.kind == PortKind.STRING:
            assert isinstance(value, str), f"Expected str got {value}"
            return str(value)

        if port.kind == PortKind.ENUM:
            assert isinstance(value, Enum), f"Expected str got {value}"
            return value.name

        raise NotImplementedError(f"Should be implemented by subclass {port}")

    except Exception as e:
        raise PortShrinkingError(f"Couldn't shrink value {value} with port {port}") from e


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

    assert len(action.returns) == len(
        returns
    ), (  # We are dealing with a single output, convert it to a proper port like structure
        f"Mismatch in Return Length: expected {len(action.returns)} got {len(returns)}"
    )

    if not skip_shrinking:
        shrinked_returns_future = [
            ashrink_return(port, val, structure_registry, shelver=shelver)
            for port, val in zip(action.returns, returns)
        ]
        try:
            shrinked_returns = await asyncio.gather(*shrinked_returns_future)
            return {port.key: val for port, val in zip(action.returns, shrinked_returns)}
        except Exception as e:
            raise ShrinkingError(f"Couldn't shrink Returns {returns}: {str(e)}") from e
    else:
        return {port.key: val for port, val in zip(action.returns, returns)}
