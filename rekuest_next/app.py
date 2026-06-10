"""Global App Registry for Rekuest Next.

This module provides a single unified registry that holds every piece of agent
registration data — implementations, states and bloks — together with the hooks
and structure registries.
"""

from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from rekuest_next.actors.types import ActorBuilder
from rekuest_next.agents.hooks.registry import HooksRegistry
from rekuest_next.api.schema import (
    BlokImplementationInput,
    ComponentNodeInput,
    ImplementAgentInput,
    ImplementationInput,
    LockDefinitionInput,
    LockImplementationInput,
    StateImplementationInput,
)
from rekuest_next.protocols import AnyState
from rekuest_next.structures.registry import StructureRegistry


T = TypeVar("T")


class AppRegistry(BaseModel):
    """The single registry that consolidates all agent registration data.

    The AppRegistry stores function implementations, observable states and bloks,
    and exposes both the storage methods (used by the ``@register``/``@state``
    decorators and the agent) and the decorator surface itself.

    Example:
        ```python
        app = AppRegistry()

        @app.register
        def my_function(x: int) -> int:
            return x * 2

        @app.state
        class MyState:
            value: int
        ```
    """

    # --- implementations (formerly DefinitionRegistry) ---
    implementations: Dict[str, ImplementationInput] = Field(
        default_factory=dict, exclude=True
    )
    actor_builders: Dict[str, ActorBuilder] = Field(default_factory=dict, exclude=True)

    # --- states (formerly StateRegistry) ---
    states: Dict[str, StateImplementationInput] = Field(
        default_factory=dict, exclude=True
    )
    state_registry_schemas: Dict[str, StructureRegistry] = Field(
        default_factory=dict, exclude=True
    )
    state_interface_classes: Dict[str, AnyState] = Field(
        default_factory=dict, exclude=True
    )
    state_classes_interfaces: Dict[Type[AnyState], str] = Field(
        default_factory=dict, exclude=True
    )

    # --- bloks (formerly BlokRegistry) ---
    registered_bloks: Dict[str, ComponentNodeInput] = Field(default_factory=dict)
    registered_blok_descriptions: Dict[str, str | None] = Field(default_factory=dict)
    registered_blok_demo_states: Dict[str, Dict[str, Any] | None] = Field(
        default_factory=dict
    )

    # --- other registries kept as composed fields ---
    hooks_registry: HooksRegistry = Field(default_factory=HooksRegistry)
    structure_registry: StructureRegistry = Field(default_factory=StructureRegistry)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # ------------------------------------------------------------------ #
    # Implementation storage                                             #
    # ------------------------------------------------------------------ #
    def register_at_interface(
        self,
        interface: str,
        implementation: ImplementationInput,
        actorBuilder: ActorBuilder,
    ) -> None:
        """Register a function or generator at the given interface."""
        self.implementations[interface] = implementation
        self.actor_builders[interface] = actorBuilder

    def get_implementations(self) -> List[ImplementationInput]:
        """Get all implementations in the registry."""
        return list(self.implementations.values())

    def get_builder_for_interface(self, interface: str) -> ActorBuilder:
        """Get the actor builder for a given interface."""
        return self.actor_builders[interface]

    def get_locks(self) -> List[LockImplementationInput]:
        """Get all lock implementations referenced by the implementations."""
        lock_implementations: Dict[str, LockImplementationInput] = {}
        for schema in self.implementations.values():
            if schema.locks is not None:
                for lock in schema.locks:
                    if lock not in lock_implementations:
                        lock_implementations[lock] = LockImplementationInput(
                            key=lock,
                            definition=LockDefinitionInput(
                                key=lock,
                                description=f"Lock definition for {lock}",
                            ),
                        )
        return list(lock_implementations.values())

    # ------------------------------------------------------------------ #
    # State storage                                                      #
    # ------------------------------------------------------------------ #
    def register_state(
        self,
        cls: Type[AnyState],
        state: StateImplementationInput,
        registry: StructureRegistry,
    ) -> None:
        """Register a state schema at its interface."""
        self.states[state.interface] = state
        self.state_registry_schemas[state.interface] = registry
        self.state_classes_interfaces[cls] = state.interface
        self.state_interface_classes[state.interface] = cls

    def get_registry_for_interface(self, interface: str) -> StructureRegistry:
        """Get the structure registry for a state interface."""
        assert interface in self.state_registry_schemas, "No definition for interface"
        return self.state_registry_schemas[interface]

    def get_interface_for_class(self, cls: Type[AnyState]) -> str:
        """Get the interface for a state class."""
        assert cls in self.state_classes_interfaces, "No definition for class"
        return self.state_classes_interfaces[cls]

    # ------------------------------------------------------------------ #
    # Blok storage                                                       #
    # ------------------------------------------------------------------ #
    def register_blok(
        self,
        name: str,
        component: Optional[str | ComponentNodeInput] = None,
        description: Optional[str] = None,
        demo_state: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a blok component tree in the registry."""
        from rekuest_next.blok.parser import jsx as parse_jsx

        if not name:
            raise ValueError("A blok name is required")
        if component is None:
            raise ValueError(f"Blok '{name}' must define a component")
        if isinstance(component, str):
            component = parse_jsx(component)

        self.registered_bloks[name] = component
        self.registered_blok_descriptions[name] = description
        self.registered_blok_demo_states[name] = demo_state

    def get_declared_bloks(self) -> Dict[str, BlokImplementationInput]:
        """Generate blok inputs from their declarations against this registry."""
        from rekuest_next.blok.registry import build_declared_bloks

        return build_declared_bloks(self)

    # ------------------------------------------------------------------ #
    # Agent input assembly                                               #
    # ------------------------------------------------------------------ #
    def to_implement_agent_input(
        self,
        instance_id: str,
        name: Optional[str] = None,
    ) -> ImplementAgentInput:
        """Assemble (and validate) the full agent input from this registry.

        Constructing the :class:`ImplementAgentInput` triggers its model
        validation, so this is the single validated retrieval point for
        everything the agent registers.
        """
        return ImplementAgentInput(
            instance_id=instance_id,
            name=name,
            implementations=tuple(self.get_implementations()),
            states=tuple(self.states.values()),
            locks=tuple(self.get_locks()),
            bloks=tuple(self.get_declared_bloks().values()),
        )

    # ------------------------------------------------------------------ #
    # Decorators                                                         #
    # ------------------------------------------------------------------ #
    def state(
        self,
        *args: Type[T],
        name: Optional[str] = None,
    ) -> Type[T] | Callable[[Type[T]], Type[T]]:
        """Register a class as a stateful entity."""
        from rekuest_next.state.decorator import state as state_decorator

        return state_decorator(
            *args,
            name=name,
            registry=self,
            structure_reg=self.structure_registry,
        )

    def background(
        self,
        *args: T,
        name: Optional[str] = None,
    ) -> T | Callable[[T], T]:
        """Register a background task."""
        from rekuest_next.agents.hooks.background import (
            background as background_decorator,
        )

        if args:
            return background_decorator(*args, name=name, registry=self.hooks_registry)

        def decorator(func: T) -> T:
            return background_decorator(func, name=name, registry=self.hooks_registry)

        return decorator

    def startup(
        self,
        *args: T,
        name: Optional[str] = None,
    ) -> T | Callable[[T], T]:
        """Register a startup hook."""
        from rekuest_next.agents.hooks.startup import startup as startup_decorator

        if args:
            return startup_decorator(*args, name=name, registry=self.hooks_registry)

        def decorator(func: T) -> T:
            return startup_decorator(func, name=name, registry=self.hooks_registry)

        return decorator

    def context(
        self,
        *args: Type[T],
    ) -> Type[T] | Callable[[Type[T]], Type[T]]:
        """Mark a class as a context."""
        from rekuest_next.agents.context import context as context_decorator

        if args:
            return context_decorator(*args)

        def decorator(cls: Type[T]) -> Type[T]:
            return context_decorator(cls)

        return decorator

    def register(
        self,
        *args: T,
        interface: Optional[str] = None,
        **kwargs: Any,
    ) -> T | Callable[[T], T]:
        """Register a function or class as an implementation."""
        from rekuest_next.register import register as register_decorator

        if args:
            return register_decorator(
                *args,
                interface=interface,
                implementation_registry=self,
                structure_registry=self.structure_registry,
                **kwargs,
            )

        def decorator(func: T) -> T:
            return register_decorator(
                func,
                interface=interface,
                implementation_registry=self,
                structure_registry=self.structure_registry,
                **kwargs,
            )

        return decorator


# Global app registry instance
_GLOBAL_APP_REGISTRY: Optional[AppRegistry] = None


def get_default_app_registry() -> AppRegistry:
    """Return the process-wide default :class:`AppRegistry` instance."""
    global _GLOBAL_APP_REGISTRY
    if _GLOBAL_APP_REGISTRY is None:
        _GLOBAL_APP_REGISTRY = AppRegistry()
    return _GLOBAL_APP_REGISTRY


def set_default_app_registry(registry: AppRegistry) -> None:
    """Replace the process-wide default :class:`AppRegistry` instance."""
    global _GLOBAL_APP_REGISTRY
    _GLOBAL_APP_REGISTRY = registry


def reset_default_app_registry() -> None:
    """Clear the cached default :class:`AppRegistry` singleton."""
    global _GLOBAL_APP_REGISTRY
    _GLOBAL_APP_REGISTRY = None


__all__ = [
    "AppRegistry",
    "get_default_app_registry",
    "set_default_app_registry",
    "reset_default_app_registry",
]
