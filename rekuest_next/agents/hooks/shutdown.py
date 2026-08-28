"""Hooks for the agent"""

import inspect
from typing import (
    Any,
    TypeVar,
    cast,
    get_type_hints,
    overload,
)
from collections.abc import Callable
import asyncio

from koil.bridge import run_threaded
from rekuest_next.state.publish import StateHolder
from rekuest_next.agents.hooks.registry import (
    HooksRegistry,
    get_default_hook_registry,
)
from rekuest_next.agents.hooks.variables import WithVariables
from rekuest_next.protocols import (
    AnyFunction,
    AsyncShutdownFunction,
    ShutdownFunction,
    ThreadedShutdownFunction,
)
from rekuest_next.definition.define import is_none_type
from rekuest_next.state.publish import direct_publishing
from rekuest_next.state.utils import is_empty_type


class ShutdownWithVariables(WithVariables):
    """Shutdown hooks may take anything but must not return: the agent is tearing down."""

    hook_kind = "Shutdown"

    def validate_returns(self, func: AnyFunction) -> None:
        # Resolve the hints first: an unresolved ``-> None`` annotation is the literal
        # None, which get_return_length would count as a return value.
        try:
            hints = get_type_hints(func, include_extras=True)
        except Exception:
            hints = {}
        returns = hints.get("return", inspect.signature(func).return_annotation)

        if not (is_none_type(returns) or is_empty_type(returns)):
            raise ValueError(
                f"Shutdown function {func.__name__} must not return anything, but returns {returns}. "
                "The agent is tearing down, so returned states and contexts would never be used."
            )


class WrappedShutdownHook(ShutdownWithVariables):
    """Shutdown hook that runs in the event loop"""

    def __init__(self, func: AsyncShutdownFunction) -> None:
        """Initialize the shutdown hook

        Args:
            func (Callable): The function to run when the agent tears down
        """
        super().__init__(func)

    async def arun(
        self,
        agent: StateHolder,
        contexts: dict[str, Any],
        states: dict[str, Any],
        app_context: Any,
    ) -> None:
        """Run the shutdown hook in the event loop"""
        kwargs = self.get_kwargs(contexts, states, app_context)
        with direct_publishing(agent):
            await self.func(**kwargs)


class ThreadedShutdownHook(ShutdownWithVariables):
    """Shutdown hook that runs in a thread"""

    def __init__(self, func: ThreadedShutdownFunction) -> None:
        """Initialize the shutdown hook

        Args:
            func (Callable): The function to run when the agent tears down
        """
        super().__init__(func)

    def run_with_publishing(self, agent: StateHolder, **kwargs: Any) -> None:
        with direct_publishing(agent):
            self.func(**kwargs)

    async def arun(
        self,
        agent: StateHolder,
        contexts: dict[str, Any],
        states: dict[str, Any],
        app_context: Any,
    ) -> None:
        """Run the shutdown hook in a thread"""
        kwargs = self.get_kwargs(contexts, states, app_context)
        await run_threaded(
            self.run_with_publishing,
            agent,
            **kwargs,  # type: ignore[arg-type]
        )


TShutdown = TypeVar("TShutdown", bound=ShutdownFunction)


@overload
def shutdown(*args: TShutdown) -> TShutdown:
    """Decorator to register a shutdown hook"""

    ...


@overload
def shutdown(
    *, name: str | None = None, registry: HooksRegistry | None = None
) -> Callable[[TShutdown], TShutdown]:
    """Decorator to register a shutdown hook

    Args:
        name (str): The name of the shutdown hook. If not provided, the function name will be used.
        registry (HooksRegistry): The registry to use. If not provided, the default registry will be used.
    """
    ...


@overload
def shutdown(
    *args: TShutdown,
    name: str | None = None,
    registry: HooksRegistry | None = None,
) -> TShutdown | Callable[[TShutdown], TShutdown]:
    """Decorator to register a shutdown hook"""


# --- Implementation ---
def shutdown(
    *args: TShutdown,
    name: str | None = None,
    registry: HooksRegistry | None = None,
) -> TShutdown | Callable[[TShutdown], TShutdown]:
    """Register a shutdown hook on the selected hook registry.

    Shutdown hooks run when the agent tears down, in the reverse of the order they
    were registered, and are the counterpart of ``startup`` hooks: they release
    whatever the app acquired while it was running. They run on every teardown,
    including the ones caused by an error or a cancellation, but only if the agent
    got far enough to run its startup hooks.

    The signature is inspected for state, context, and app-context dependencies so
    the runtime can inject the live values the agent is about to drop. A shutdown
    hook must not return anything.

    Async shutdown hooks run directly in the event loop. Synchronous shutdown hooks
    are wrapped in ``ThreadedShutdownHook`` and executed through ``run_threaded`` so
    they do not block the loop. Both run inside ``direct_publishing`` so state
    mutations are propagated immediately.

    A hook that raises is logged and the remaining hooks still run: teardown never
    fails because of a shutdown hook.

    Args:
        *args: Shutdown function to register when used as ``@shutdown`` without
            parentheses.
        name: Explicit registry key. Defaults to the function name.
        registry: Hook registry to populate. Defaults to the global hook
            registry.

    Returns:
        The original function, or a decorator configured with the provided
        metadata.

    Raises:
        ValueError: If more than one function is passed at once.

    Examples:
        Close a client that a startup hook put on a context::

            @shutdown
            async def teardown(my_context: MyContext) -> None:
                await my_context.client.aclose()
    """

    if len(args) > 1:
        raise ValueError("You can only register one function at a time.")

    if len(args) == 1:
        func = args[0]
        registry = registry or get_default_hook_registry()

        if asyncio.iscoroutinefunction(func):
            a = cast(AsyncShutdownFunction, func)
            registry.register_shutdown(name or a.__name__, WrappedShutdownHook(a))

        else:
            assert inspect.isfunction(func) or inspect.ismethod(func), (
                "Function must be a async function or a sync function"
            )
            t = cast(ThreadedShutdownFunction, func)

            registry.register_shutdown(name or t.__name__, ThreadedShutdownHook(t))

        return cast(TShutdown, func)
    else:

        def decorator(func: TShutdown) -> TShutdown:
            return cast(TShutdown, shutdown(func, name=name, registry=registry))

        return decorator
