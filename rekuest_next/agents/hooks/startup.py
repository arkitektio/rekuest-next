"""Hooks for the agent"""

import contextvars
import inspect
from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    TypeVar,
    cast,
    overload,
)
from janus import T
import asyncio

from koil.helpers import run_spawned
from rekuest_next.agents.context import get_context_name, is_context
from rekuest_next.agents.hooks.errors import StartupHookError
from rekuest_next.agents.hooks.registry import (
    HooksRegistry,
    StartupHook,
    StartupHookReturns,
    get_default_hook_registry,
)
from rekuest_next.protocols import (
    AsyncStartupFunction,
    ThreadedStartupFunction,
    StartupFunction,
)
from rekuest_next.remote import ensure_return_as_tuple
from rekuest_next.state.predicate import get_state_name, is_state


startup_context = contextvars.ContextVar("startup_hook_context")


class WrappedStartupHook(StartupHook):
    """Startup hook that runs in the event loop"""

    def __init__(self, func: AsyncStartupFunction) -> None:
        """Initialize the startup hook

        Args:
            func (Callable[[str, Any], AnyContext]): The function to run in the startup hook
            func (Callable): The function to run in the startup hook
        """
        self.func = func
        self.pass_instance_id = False

        # check if has context argument
        arguments = inspect.signature(func).parameters
        if len(arguments) > 1:
            raise StartupHookError(
                "Startup hook must have exactly one argument (app_context) or no arguments"
            )
        if len(arguments) == 1:
            self.pass_app_context = True

    async def arun(self, instance_id: str, app_context: Any) -> StartupHookReturns:
        """Run the startup hook in the event loop
        Args:
            instance_id (str): The instance id of the agent
            app_context (Any): The context for the startup hook
        Returns:
            Optional[Dict[str, Any]]: The state variables and contexts
        """
        token = startup_context.set(app_context)

        try:
            if self.pass_app_context:
                parsed_returns = await self.func(app_context)
            else:
                parsed_returns = await self.func()
        finally:
            startup_context.reset(token)
        returns = ensure_return_as_tuple(parsed_returns)

        states: Dict[str, Any] = {}
        contexts: Dict[str, Any] = {}

        for return_value in returns:
            if is_state(return_value):
                states[get_state_name(return_value)] = return_value
            elif is_context(return_value):
                print("Registering context:", get_context_name(return_value))
                contexts[get_context_name(return_value)] = return_value
            else:
                raise StartupHookError(
                    "Startup hook must return state or context variables. Other returns are not allowed"
                )

        return StartupHookReturns(states=states, contexts=contexts)


class ThreadedStartupHook(StartupHook):
    """Startup hook that runs in the event loop"""

    def __init__(self, func: ThreadedStartupFunction) -> None:
        """Initialize the startup hook

        Args:
            func (Callable[[str], AnyContext]): The function to run in the startup hook
            func (Callable): The function to run in the startup hook
        """
        self.func = func
        self.pass_instance_id = False

        # check if has context argument
        arguments = inspect.signature(func).parameters
        if len(arguments) > 1:
            raise StartupHookError(
                "Startup hook must have exactly one argument (app_context) or no arguments"
            )
        if len(arguments) == 1:
            self.pass_app_context = True

    def run_func_with_context(self, app_context: Any) -> Any:
        token = startup_context.set(app_context)
        try:
            if self.pass_app_context:
                return self.func(app_context)
            else:
                return self.func()
        finally:
            startup_context.reset(token)

    async def arun(self, instance_id: str, app_context: Any) -> StartupHookReturns:
        """Run the startup hook in the event loop
        Args:
            instance_id (str): The instance id of the agent
            app_context (Any): The context for the startup hook
        Returns:
            Optional[Dict[str, Any]]: The state variables and contexts
        """
        parsed_returns = await run_spawned(self.run_func_with_context, app_context)

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


@overload
def startup(
    *args: TStartup,
    name: Optional[str] = None,
    registry: Optional[HooksRegistry] = None,
) -> TStartup | Callable[[TStartup], TStartup]:
    """Decorator to register a startup hook"""


# --- Implementation ---
def startup(
    *args: TStartup,
    name: Optional[str] = None,
    registry: Optional[HooksRegistry] = None,
) -> TStartup | Callable[[TStartup], TStartup]:
    """Decorator to register a startup hook

    Args:
        name (str): The name of the startup hook. If not provided, the function name will be used.
        registry (HooksRegistry): The registry to use. If not provided, the default registry will be used.
    """

    if len(args) > 1:
        raise ValueError("You can only register one function at a time.")

    if len(args) == 1:
        func = args[0]
        registry = registry or get_default_hook_registry()

        if inspect.iscoroutinefunction(func):
            registry.register_startup(name or func.__name__, WrappedStartupHook(func))

        else:
            assert inspect.isfunction(func) or inspect.ismethod(func), (
                "Function must be a async function or a sync function"
            )
            t = cast(ThreadedStartupFunction, func)

            registry.register_startup(name or func.__name__, ThreadedStartupHook(t))

        return func  # type: ignore
    else:

        def decorator(func: T) -> T:
            registry = get_default_hook_registry()

            if asyncio.iscoroutinefunction(func):
                registry.register_startup(func.__name__, WrappedStartupHook(func))

            else:
                assert inspect.isfunction(func), (
                    "Function must be a async function or a sync function"
                )

                t = cast(ThreadedStartupFunction, func)
                registry.register_startup(func.__name__, ThreadedStartupHook(t))
            return func

        return decorator
