"""Decorator to register a class as a state."""

from dataclasses import dataclass, is_dataclass
from typing import Optional, Type, TypeVar, Callable, overload, Any, List
from rekuest_next.api.schema import PortInput, StateSchemaInput
from rekuest_next.state.observable import StateConfig, make_evented
from rekuest_next.state.publish import get_current_publisher, noop_publisher
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.state.registry import StateRegistry, get_default_state_registry
from rekuest_next.structures.default import get_default_structure_registry
from rekuest_next.protocols import AnyState
from fieldz import fields, Field

T = TypeVar("T", bound=AnyState)


def inspect_state_schema(
    cls: Type[T], structure_registry: StructureRegistry
) -> StateSchemaInput:
    """Inspect the state schema of a class."""
    from rekuest_next.definition.define import convert_object_to_port

    ports: list[PortInput] = []

    for field in fields(cls):  # type: ignore
        type_ = field.type or field.annotated_type
        if type_ is None:
            raise ValueError(
                f"Field {field.name} has no type annotation. Please add a type annotation."
            )

        port = convert_object_to_port(
            cls=type_,
            key=field.name,
            description=field.description or field.metadata.get("description", None),
            validators=field.metadata.get("validators", None),
            label=field.metadata.get("label", None),
            default=field.default if field.default != Field.MISSING else None,
            registry=structure_registry,
        )
        ports.append(port)

    return StateSchemaInput(ports=tuple(ports), name=getattr(cls, "__rekuest_state__"))


def statify(
    cls: Type[T],
    required_locks: Optional[list[str]] = None,
    structure_registry: Optional[StructureRegistry] = None,
    publish_interval: float = 0.1,
) -> tuple[Type[T], StateSchemaInput]:
    if structure_registry is None:
        structure_registry = get_default_structure_registry()

    state_schema = inspect_state_schema(cls, structure_registry)

    config = StateConfig(
        state_schema=state_schema,
        state_name=getattr(cls, "__rekuest_state__", cls.__name__),
        publish_interval=publish_interval,
        required_locks=required_locks or [],
        structure_registry=structure_registry,
    )

    original_init = getattr(cls, "__init__", lambda self: None)

    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        make_evented(self, config, "")

    cls.__init__ = new_init

    setattr(cls, "__rekuest_state_config__", config)

    return cls, state_schema


# --- 5. The State Decorator ---


@overload
def state(*function: Type[T]) -> Type[T]: ...


@overload
def state(
    *,
    name: Optional[str] = None,
    local_only: bool = False,
    required_locks: Optional[list[str]] = None,
    publish_interval: float = 0.1,
    registry: Optional[StateRegistry] = None,
    structure_reg: Optional[StructureRegistry] = None,
) -> Callable[[T], T]: ...


def state(
    *function: Type[T],
    local_only: bool = False,
    name: Optional[str] = None,
    required_locks: Optional[list[str]] = None,
    publish_interval: float = 0.1,
    registry: Optional[StateRegistry] = None,
    structure_reg: Optional[StructureRegistry] = None,
) -> Type[T] | Callable[[Type[T]], Type[T]]:
    """
    Decorator to register a class as a state.
    """
    registry = registry or get_default_state_registry()
    structure_registry = structure_reg or get_default_structure_registry()

    if len(function) == 1:
        cls = function[0]
        return state(name=cls.__name__)(cls)

    if len(function) == 0:

        def wrapper(cls: Type[T]) -> Type[T]:
            # Ensure it's a dataclass
            try:
                fields(cls)
            except TypeError:
                cls = dataclass(cls)

            setattr(cls, "__rekuest_state__", cls.__name__ if name is None else name)

            # Apply Statify Logic
            cls, state_schema = statify(
                cls,
                required_locks=required_locks,
                structure_registry=structure_registry,
                publish_interval=publish_interval,
            )

            print(f"✅ Registered state '{name or cls.__name__}'")

            registry.register_at_interface(
                name or cls.__name__, cls, state_schema, structure_registry
            )
            return cls

        return wrapper

    raise ValueError("You can only register one class at a time.")
