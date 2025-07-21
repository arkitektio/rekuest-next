"""Decorator to register a class as a state."""

from dataclasses import dataclass
from rekuest_next.api.schema import PortInput
from typing import Optional, Type, TypeVar, Callable, overload
from fieldz import fields  # type: ignore
from rekuest_next.protocols import AnyState
from rekuest_next.structures.registry import (
    StructureRegistry,
)

from rekuest_next.state.registry import (
    StateRegistry,
    get_default_state_registry,
)
from rekuest_next.api.schema import StateSchemaInput
from rekuest_next.structures.default import get_default_structure_registry

T = TypeVar("T", bound=AnyState)


def inspect_state_schema(cls: Type[T], structure_registry: StructureRegistry) -> StateSchemaInput:
    """Inspect the state schema of a class."""
    from rekuest_next.definition.define import convert_object_to_port

    ports: list[PortInput] = []

    for field in fields(cls):  # type: ignore
        type = field.type or field.annotated_type  # type: ignore
        if type is None:
            raise ValueError(
                f"Field {field.name} has no type annotation. Please add a type annotation."
            )

        port = convert_object_to_port(type, field.name, structure_registry)  # type: ignore
        ports.append(port)

    return StateSchemaInput(ports=tuple(ports), name=getattr(cls, "__rekuest_state__"))


@overload
def state(
    *function: Type[T],
) -> Type[T]: ...


@overload
def state(
    *,
    name: Optional[str] = None,
    local_only: bool = False,
    registry: Optional[StateRegistry] = None,
    structure_reg: Optional[StructureRegistry] = None,
) -> Callable[[T], T]: ...


def state(  # type: ignore[valid-type]
    *function: Type[T],
    local_only: bool = False,
    name: Optional[str] = None,
    registry: Optional[StateRegistry] = None,
    structure_reg: Optional[StructureRegistry] = None,
) -> Type[T] | Callable[[Type[T]], Type[T]]:
    """Decorator to register a class as a state.

    Args:
        name_or_function (Type[T]): The class to register
        local_only (bool): If True, the state will only be available locally.
        name (Optional[str]): The name of the state. If None, the class name will be used.
        registry (Optional[StateRegistry]): The state registry to use. If None, the current state registry will be used.
        structure_reg (Optional[StructureRegistry]): The structure registry to use. If None, the default structure registry will be used.


    Returns:
        Callable[[Type[T]], Type[T]]: The decorator function.


    """
    registry = registry or get_default_state_registry()
    structure_registry = structure_reg or get_default_structure_registry()

    if len(function) == 1:
        cls = function[0]
        return state(name=cls.__name__)(cls)

    if len(function) == 0:

        def wrapper(cls: Type[T]) -> Type[T]:
            try:
                fields(cls)
            except TypeError:
                cls = dataclass(cls)

            setattr(cls, "__rekuest_state__", name)
            setattr(cls, "__rekuest_state_local__", local_only)

            state_schema = inspect_state_schema(cls, structure_registry)

            registry.register_at_interface(
                name or cls.__name__, cls, state_schema, structure_registry
            )

            return cls

        return wrapper

    raise ValueError("You can only register one class at a time.")
