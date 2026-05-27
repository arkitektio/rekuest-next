"""Global App Registry for Rekuest Next.

This module provides a unified registry that consolidates all the different
registries (definition, hooks, state, structure) into one unified registry.
"""

from typing import Any, Callable, Optional, Type, TypeVar

from pydantic import BaseModel, Field

from rekuest_next.api.schema import ComponentNodeInput
from rekuest_next.blok.registry import BlokRegistry
from rekuest_next.definition.registry import DefinitionRegistry
from rekuest_next.agents.hooks.registry import HooksRegistry
from rekuest_next.state.registry import StateRegistry
from rekuest_next.structures.registry import StructureRegistry


T = TypeVar("T")


class AppRegistry(BaseModel):
    """A unified registry that consolidates all component registries.

    The AppRegistry provides a single point of access for registering
    functions, states, hooks, and background tasks. It wraps all the
    individual registries and provides convenience methods that delegate
    to the appropriate decorator functions.

    Example:
        ```python
        app = AppRegistry()

        @app.register
        def my_function(x: int) -> int:
            return x * 2

        @app.state
        class MyState:
            value: int

        @app.startup
        async def my_startup():
            return MyState(value=0)

        @app.background
        async def my_background(state: MyState):
            while True:
                await asyncio.sleep(1)
        ```

    Attributes:
        implementation_registry: Registry for function implementations.
        hooks_registry: Registry for startup and background hooks.
        state_registry: Registry for state schemas.
        structure_registry: Registry for structure converters.
    """

    implementation_registry: DefinitionRegistry = Field(
        default_factory=DefinitionRegistry
    )
    hooks_registry: HooksRegistry = Field(default_factory=HooksRegistry)
    state_registry: StateRegistry = Field(default_factory=StateRegistry)
    structure_registry: StructureRegistry = Field(default_factory=StructureRegistry)
    blok_registry: BlokRegistry = Field(default_factory=BlokRegistry)

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True

    def state(
        self,
        *args: Type[T],
        name: Optional[str] = None,
        local_only: bool = False,
    ) -> Type[T] | Callable[[Type[T]], Type[T]]:
        """Register a class as a stateful entity.

        State classes are used to store information that should be visible
        to the user and might change between action calls.

        Args:
            *args: The class to register (when used without parentheses).
            name: Optional name for the state. Defaults to class name.
            local_only: If True, the state will only be available locally.

        Returns:
            The decorated class or a decorator function.
        """
        from rekuest_next.state.decorator import state as state_decorator

        if args:
            # Called as @app.state without parentheses
            return state_decorator(
                *args,
                name=name,
                local_only=local_only,
                registry=self.state_registry,
                structure_reg=self.structure_registry,
            )
        else:
            # Called as @app.state() with parentheses
            def decorator(cls: Type[T]) -> Type[T]:
                return state_decorator(
                    cls,
                    name=name,
                    local_only=local_only,
                    registry=self.state_registry,
                    structure_reg=self.structure_registry,
                )

            return decorator

    def background(
        self,
        *args: T,
        name: Optional[str] = None,
    ) -> T | Callable[[T], T]:
        """Register a background task.

        Background tasks are functions that run continuously in the background
        as asyncio tasks. They are started when the agent starts up and stopped
        automatically when the agent shuts down.

        Args:
            *args: The function to register (when used without parentheses).
            name: Optional name for the task. Defaults to function name.

        Returns:
            The decorated function or a decorator function.
        """
        from rekuest_next.agents.hooks.background import (
            background as background_decorator,
        )

        if args:
            return background_decorator(*args, name=name, registry=self.hooks_registry)
        else:

            def decorator(func: T) -> T:
                return background_decorator(
                    func, name=name, registry=self.hooks_registry
                )

            return decorator

    def startup(
        self,
        *args: T,
        name: Optional[str] = None,
    ) -> T | Callable[[T], T]:
        """Register a startup hook.

        Startup hooks are functions that run when the agent starts up.
        They can return state and context objects that will be available
        to other functions.

        Args:
            *args: The function to register (when used without parentheses).
            name: Optional name for the hook. Defaults to function name.

        Returns:
            The decorated function or a decorator function.
        """
        from rekuest_next.agents.hooks.startup import startup as startup_decorator

        if args:
            return startup_decorator(*args, name=name, registry=self.hooks_registry)
        else:

            def decorator(func: T) -> T:
                return startup_decorator(func, name=name, registry=self.hooks_registry)

            return decorator

    def context(
        self,
        *args: Type[T],
    ) -> Type[T] | Callable[[Type[T]], Type[T]]:
        """Mark a class as a context.

        Context classes are used to pass shared resources (like database
        connections) to functions that need them.

        Args:
            *args: The class to register (when used without parentheses).

        Returns:
            The decorated class or a decorator function.
        """
        from rekuest_next.agents.context import context as context_decorator

        if args:
            return context_decorator(*args)
        else:

            def decorator(cls: Type[T]) -> Type[T]:
                return context_decorator(cls)

            return decorator

    def register(
        self,
        *args: T,
        interface: Optional[str] = None,
        **kwargs: Any,
    ) -> T | Callable[[T], T]:
        """Register a function or class as an implementation.

        This is the main decorator for registering functions that should
        be exposed as actions in the rekuest system.

        Args:
            *args: The function to register (when used without parentheses).
            interface: Optional interface name. Defaults to function name.
            **kwargs: Additional arguments passed to the register decorator.

        Returns:
            The decorated function or a decorator function.
        """
        from rekuest_next.register import register as register_decorator

        if args:
            return register_decorator(
                *args,
                interface=interface,
                implementation_registry=self.implementation_registry,
                structure_registry=self.structure_registry,
                **kwargs,
            )
        else:

            def decorator(func: T) -> T:
                return register_decorator(
                    func,
                    interface=interface,
                    implementation_registry=self.implementation_registry,
                    structure_registry=self.structure_registry,
                    **kwargs,
                )

            return decorator

    def register_blok(
        self,
        name: str,
        component: Optional[str | ComponentNodeInput] = None,
        description: Optional[str] = None,
        demo_state: Optional[dict] = None,
    ) -> None:
        """Register a function or class as a Blok implementation.

        This is the main decorator for registering functions that should
        be exposed as Bloks in the rekuest system.

        Args:
            *args: The function to register (when used without parentheses).
            name: Optional name for the Blok. Defaults to function name.


        """
        self.blok_registry.register_blok(
            name=name,
            component=component,
            description=description,
            demo_state=demo_state,
        )

    def validate(self) -> None:
        """Validate the registries to ensure there are no conflicts or issues."""
        self.blok_registry.get_declared_bloks()


# Global app registry instance
_GLOBAL_APP_REGISTRY: Optional[AppRegistry] = None


def get_default_app_registry() -> AppRegistry:
    """Return the process-wide default :class:`AppRegistry` instance.

    The first call lazily creates the singleton registry. Subsequent calls reuse
    the same object until :func:`reset_default_app_registry` or
    :func:`set_default_app_registry` changes it.

    Returns:
        The default application registry singleton.

    Examples:
        Retrieve the shared registry and register an action on it::

            registry = get_default_app_registry()
            decorator = registry.register(interface="camera")
    """
    global _GLOBAL_APP_REGISTRY
    if _GLOBAL_APP_REGISTRY is None:
        _GLOBAL_APP_REGISTRY = AppRegistry()
    return _GLOBAL_APP_REGISTRY


def set_default_app_registry(registry: AppRegistry) -> None:
    """Replace the process-wide default :class:`AppRegistry` instance.

    Use this when tests or applications need an isolated registration surface
    instead of the shared singleton.

    Args:
        registry: Registry instance to install as the new default.

    Examples:
        Swap in a custom registry for a test run::

            set_default_app_registry(AppRegistry())
    """
    global _GLOBAL_APP_REGISTRY
    _GLOBAL_APP_REGISTRY = registry


def reset_default_app_registry() -> None:
    """Clear the cached default :class:`AppRegistry` singleton.

    The next call to :func:`get_default_app_registry` creates a fresh registry.

    Examples:
        Reset global registration state between tests::

            reset_default_app_registry()
    """
    global _GLOBAL_APP_REGISTRY
    _GLOBAL_APP_REGISTRY = None


__all__ = [
    "AppRegistry",
    "get_default_app_registry",
    "set_default_app_registry",
    "reset_default_app_registry",
]
