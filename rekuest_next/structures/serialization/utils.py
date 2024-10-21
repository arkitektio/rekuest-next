import asyncio
from typing import Any
from rekuest_next.api.schema import Port, PortKind
from rekuest_next.structures.errors import PortShrinkingError, StructureShrinkingError


async def aexpand(port: Port, value: Any, structure_registry=None) -> Any:
    """Expand a value through a port

    Args:
        port (ArgPort): Port to expand to
        value (Any): Value to expand
    Returns:
        Any: Expanded value

    """
    if port.kind == PortKind.DICT:
        return {
            key: await aexpand(port.child, value, structure_registry)
            for key, value in value.items()
        }

    if port.kind == PortKind.LIST:
        return await asyncio.gather(
            *[
                aexpand(port.child, item, structure_registry=structure_registry)
                for item in value
            ]
        )

    if port.kind == PortKind.INT:
        return int(value) if value is not None else int(port.default)

    if port.kind == PortKind.FLOAT:
        return float(value) if value is not None else float(port.default)

    if port.kind == PortKind.STRUCTURE:
        value = value if value is not None else port.default

        if value is None:
            assert port.nullable, "Null value not allowed for non-nullable port"
            return None

        return await structure_registry.get_expander_for_identifier(port.identifier)(
            value
        )

    if port.kind == PortKind.BOOL:
        if value is None:
            value = port.default

        return bool(value) if value is not None else None

    if port.kind == PortKind.STRING:
        if value is None:
            value = port.default

        return str(value) if value is not None else None

    raise NotImplementedError("Should be implemented by subclass")


async def ashrink(port: Port, value: Any, structure_registry=None) -> Any:
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
                key: await ashrink(port.child, value, structure_registry)
                for key, value in value.items()
            }

        if port.kind == PortKind.LIST:
            return await asyncio.gather(
                *[
                    ashrink(port.child, item, structure_registry=structure_registry)
                    for item in value
                ]
            )

        if port.kind == PortKind.INT:
            return int(value) if value is not None else None

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
