"""Decorator to register a class as a state."""

from dataclasses import dataclass
from rekuest_next.api.schema import PortInput
from typing import Optional, Type, TypeVar, Callable, overload, Any
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


def statify(cls: Type[T], required_locks: Optional[list[str]] = None) -> Type[T]:
    """Alias for state decorator."""

    def new_get_attribute(self, name: str) -> Any:
        if name == "is_state":
            return True
        return super(cls, self).__getattribute__(name)

    def new_set_attribute(self, name: str, value: Any) -> None:
        from rekuest_next.actors.context import get_current_assignation_helper
        from rekuest_next.actors.errors import NotWithinAnAssignationError
        from rekuest_next.agents.hooks.startup import startup_context

        try:
            assignation_helper = get_current_assignation_helper()
            if assignation_helper is None:
                raise RuntimeError(
                    "You CANNOT set state attributes outside of an action context. This is an anti-pattern."
                )

            actor = assignation_helper.actor
            if required_locks:
                missing_locks = actor.missing_locks(required_locks)
                if missing_locks:
                    raise RuntimeError(
                        f"The state {cls.__name__} requires the following locks: {missing_locks} you are calling set from within a context that doesn't hold the required locks. This is an anti-pattern."
                    )

        except NotWithinAnAssignationError:
            try:
                startup_context.get()
            except LookupError:
                raise RuntimeError(
                    "You CANNOT set state attributes outside of an action or startup context. This is an anti-pattern."
                )

        super(cls, self).__setattr__(name, value)

    cls.__getattribute__ = new_get_attribute  # type: ignore
    cls.__setattr__ = new_set_attribute  # type: ignore

    return cls


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
    required_locks: Optional[list[str]] = None,
    registry: Optional[StateRegistry] = None,
    structure_reg: Optional[StructureRegistry] = None,
) -> Type[T] | Callable[[Type[T]], Type[T]]:
    """Decorator to register a class as a state.

    State classes are used to store information that should be visible to the user
    of the system and might change between action calls. Examples of state include
    the position of a robot arm, the current settings of a device, or the status of
    a process.

    State can be changed by any action if it declares it as an arguent.
    During this passing the state is locked for the duration of the action call,
    preventing race conditions. When the action has finished, the new state is published.

    If you need more fine grained control over when the state is updated, yu can always use the "publish" function
    to manually publish the state at any time.

    Attention: State is a one way street. Actions can change the state, but the state
    cannot cause actions. Its only purpose is to store information and show it to the user.

    You can also update the state in background tasks, to show sensor readings or other
    information that changes over time to the user. However, be aware that this can lead to
    race conditions if an action is changing the state at the same time. Also depending on your
    server settings, we might throttle background state updates to avoid overloading the system.




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

            setattr(cls, "__rekuest_state__", cls.__name__ if name is None else name)
            setattr(cls, "__rekuest_state_local__", local_only)

            state_schema = inspect_state_schema(cls, structure_registry)
            print("Registering state schema:", name)

            cls = statify(cls, required_locks=required_locks)

            registry.register_at_interface(
                name or cls.__name__, cls, state_schema, structure_registry
            )

            return cls

        return wrapper

    raise ValueError("You can only register one class at a time.")
