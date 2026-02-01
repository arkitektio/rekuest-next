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
from rekuest_next.agents.context import (
    prepare_context_variables,
)
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
from rekuest_next.state.utils import get_return_length, prepare_state_variables


startup_context: contextvars.ContextVar[bool] = contextvars.ContextVar("startup_hook_context")


class InspectHookMixin:
    """Mixin to inspect the hook function"""


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
        self.signature = inspect.signature(func)
        arguments = self.signature.parameters
        if len(arguments) > 1:
            raise StartupHookError(
                "Startup hook must have exactly one argument (app_context) or no arguments"
            )
        if len(arguments) == 1:
            self.pass_app_context = True

        self.return_length = get_return_length(self.signature)

        self.state_variables, self.state_returns = prepare_state_variables(self.func)
        self.context_variables, self.context_returns = prepare_context_variables(self.func)

        assert len(self.state_variables) == 0, (
            "Threaded startup hooks cannot have state variables as arguments"
        )
        assert len(self.context_variables) == 0, (
            "Threaded startup hooks cannot have context variables as arguments"
        )

        assert (len(self.state_returns) + len(self.context_returns)) == self.return_length, (
            "Threaded startup can only return state and context variables"
        )

    async def arun(self, instance_id: str, app_context: Any) -> StartupHookReturns:
        """Run the startup hook in the event loop
        Args:
            instance_id (str): The instance id of the agent
            app_context (Any): The context for the startup hook
        Returns:
            Optional[Dict[str, Any]]: The state variables and contexts
        """
        token = startup_context.set(True)

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

        for index, return_value in enumerate(returns):
            print("Processing return value:", return_value, "index:", index)
            if index in self.state_returns:
                states[self.state_returns[index]] = return_value
            elif index in self.context_returns:
                contexts[self.context_returns[index]] = return_value
            else:
                raise StartupHookError(
                    f"Startup hook must return state or context variables. Other returns are not allowed {self.context_returns}, {self.state_returns}"
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

        self.signature = inspect.signature(func)

        # check if has context argument
        arguments = self.signature.parameters
        if len(arguments) > 1:
            raise StartupHookError(
                "Startup hook must have exactly one argument (app_context) or no arguments"
            )
        if len(arguments) == 1:
            self.pass_app_context = True

        self.return_length = get_return_length(self.signature)

        self.state_variables, self.state_returns = prepare_state_variables(self.func)
        self.context_variables, self.context_returns = prepare_context_variables(self.func)

        assert len(self.state_variables) == 0, (
            "Threaded startup hooks cannot have state variables as arguments"
        )
        assert len(self.context_variables) == 0, (
            "Threaded startup hooks cannot have context variables as arguments"
        )

        assert (len(self.state_returns) + len(self.context_returns)) == self.return_length, (
            "Threaded startup can only return state and context variables"
        )

    def run_func_with_context(self, app_context: Any) -> Any:
        token = startup_context.set(True)
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

        for index, return_value in enumerate(returns):
            print("Processing return value:", return_value, "index:", index)
            if index in self.state_returns:
                states[self.state_returns[index]] = return_value
            elif index in self.context_returns:
                contexts[self.context_returns[index]] = return_value
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
