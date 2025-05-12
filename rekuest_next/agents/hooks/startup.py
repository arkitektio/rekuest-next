"""Hooks for the agent"""

import inspect
from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    TypeVar,
    overload,
)
from janus import T
import asyncio

from rekuest_next.agents.context import get_context_name, is_context
from rekuest_next.agents.hooks.errors import StartupHookError
from rekuest_next.agents.hooks.registry import (
    HooksRegistry,
    StartupHook,
    StartupHookReturns,
    get_default_hook_registry,
)
from rekuest_next.protocols import (
    StartupFunction,
)
from rekuest_next.remote import ensure_return_as_tuple
from rekuest_next.state.predicate import get_state_name, is_state


class WrappedStartupHook(StartupHook):
    """Startup hook that runs in the event loop"""

    def __init__(self, func: StartupFunction) -> None:
        """Initialize the startup hook

        Args:
            func (Callable[[str], AnyContext]): The function to run in the startup hook
            func (Callable): The function to run in the startup hook
        """
        self.func = func

        # check if has context argument
        arguments = inspect.signature(func).parameters
        if len(arguments) != 1:
            raise StartupHookError(
                "Startup hook must have exactly one argument (instance_id) or no arguments"
            )

    async def arun(self, instance_id: str) -> StartupHookReturns:
        """Run the startup hook in the event loop
        Args:
            instance_id (str): The instance id of the agent
        Returns:
            Optional[Dict[str, Any]]: The state variables and contexts
        """
        parsed_returns = await self.func(instance_id)
        returns = ensure_return_as_tuple(parsed_returns)

        states: Dict[str, Any] = {}
        contexts: Dict[str, Any] = {}

        for return_value in returns:
            if is_state(return_value):
                states[get_state_name(return_value)] = return_value
            elif is_context(return_value):
                contexts[get_context_name(return_value)] = return_value
            else:
                raise StartupHookError(
                    "Startup hook must return state or context variables. Other returns are not allowed"
                )

        return StartupHookReturns(states=states, contexts=contexts)


TStartup = TypeVar("TStartup", bound=StartupFunction)


@overload
def startup(*args: TStartup) -> TStartup:
    """Decorator to register a startup hook"""

    ...


@overload
def startup(
    *, name: Optional[str] = None, registry: Optional[HooksRegistry] = None
) -> Callable[[TStartup], TStartup]:
    """Decorator to register a startup hook

    Args:
        name (str): The name of the startup hook. If not provided, the function name will be used.
        registry (HooksRegistry): The registry to use. If not provided, the default registry will be used.
    """
    ...


# --- Implementation ---
def startup(
    *args: TStartup,
    name: Optional[str] = None,
    registry: Optional[HooksRegistry] = None,
) -> TStartup | Callable[[TStartup], TStartup]:
    if len(args) > 1:
        raise ValueError("You can only register one function at a time.")

    if len(args) == 1:
        func = args[0]
        if not asyncio.iscoroutinefunction(func):
            raise TypeError("Startup hooks must be async functions")
        registry = registry or get_default_hook_registry()
        registry.register_startup(name or func.__name__, WrappedStartupHook(func))
        return func  # type: ignore
    else:

        def decorator(func: T) -> T:
            if not asyncio.iscoroutinefunction(func):
                raise TypeError("Startup hooks must be async functions")
            reg = registry or get_default_hook_registry()
            reg.register_startup(name or func.__name__, WrappedStartupHook(func))
            return func

        return decorator
