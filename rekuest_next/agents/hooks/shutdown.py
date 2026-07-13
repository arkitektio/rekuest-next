"""Hooks for the agent"""

import inspect
from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    TypeVar,
    cast,
    get_type_hints,
    overload,
)
import asyncio

from koil.bridge import run_threaded
from rekuest_next.actors.types import Agent
from rekuest_next.agents.context import (
    prepare_context_variables,
)
from rekuest_next.agents.errors import StateRequirementsNotMet
from rekuest_next.agents.hooks.registry import (
    HooksRegistry,
    get_default_hook_registry,
)
from rekuest_next.protocols import (
    AnyFunction,
    AsyncShutdownFunction,
    ShutdownFunction,
    ThreadedShutdownFunction,
)
from rekuest_next.definition.define import is_none_type
from rekuest_next.state.publish import direct_publishing
from rekuest_next.state.utils import (
    is_empty_type,
    prepare_appcontext,
    prepare_state_variables,
)


class WithVariables:
    def __init__(self, func: AnyFunction) -> None:
        self.func = func
        self.state_variables, self.state_returns = prepare_state_variables(func)
        self.app_context_variables, self.app_context_returns = prepare_appcontext(func)
        self.context_variables, self.context_returns = prepare_context_variables(func)

        # Check the arg length of the function and raise an error if it is more than the context and state variables
        total_args = (
            self.state_variables.count
            + self.context_variables.count
            + self.app_context_variables.count
        )
        if len(inspect.signature(func).parameters) > total_args:
            incorrect_args = set(inspect.signature(func).parameters.keys()) - set(
                self.state_variables.variable_keys
                + list(self.context_variables.context_variables.keys())
                + list(self.app_context_variables.app_context_variables.keys())
            )

            raise ValueError(
                f"Shutdown function {func.__name__} has more arguments than the context and state variables. "
                f"Expected at most {total_args} arguments, but got {len(inspect.signature(func).parameters)}."
                f"{incorrect_args} are not valid argument names."
            )

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

    def get_kwargs(
        self,
        contexts: Dict[str, Any],
        states: Dict[str, Any],
        app_context: Any,
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {}
        for key, value in self.context_variables.context_variables.items():
            try:
                kwargs[key] = contexts[value]
            except KeyError as e:
                raise StateRequirementsNotMet(
                    f"Context requirements not met: {e}"
                ) from e

        for key, value in self.state_variables.read_only_variables.items():
            try:
                kwargs[key] = states[value]
            except KeyError as e:
                raise StateRequirementsNotMet(
                    f"State requirements not met: {e}. Available are {list(states.keys())}"
                ) from e

        for key, value in self.state_variables.write_state_variables.items():
            try:
                kwargs[key] = states[value]
            except KeyError as e:
                raise StateRequirementsNotMet(
                    f"State requirements not met: {e}. Available are {list(states.keys())}"
                ) from e

        for key, value in self.app_context_variables.app_context_variables.items():
            if getattr(app_context, "__rekuest_app_context__", None) != value:
                raise StateRequirementsNotMet(
                    f"App context requirements not met: the agent was not started with a {value} app context"
                )
            kwargs[key] = app_context

        return kwargs


class WrappedShutdownHook(WithVariables):
    """Shutdown hook that runs in the event loop"""

    def __init__(self, func: AsyncShutdownFunction) -> None:
        """Initialize the shutdown hook

        Args:
            func (Callable): The function to run when the agent tears down
        """
        super().__init__(func)

    async def arun(
        self,
        agent: Agent,
        contexts: Dict[str, Any],
        states: Dict[str, Any],
        app_context: Any,
    ) -> None:
        """Run the shutdown hook in the event loop"""
        kwargs = self.get_kwargs(contexts, states, app_context)
        with direct_publishing(agent):
            await self.func(**kwargs)


class ThreadedShutdownHook(WithVariables):
    """Shutdown hook that runs in a thread"""

    def __init__(self, func: ThreadedShutdownFunction) -> None:
        """Initialize the shutdown hook

        Args:
            func (Callable): The function to run when the agent tears down
        """
        super().__init__(func)

    def run_with_publishing(self, agent: Agent, **kwargs: Any) -> None:
        with direct_publishing(agent):
            self.func(**kwargs)

    async def arun(
        self,
        agent: Agent,
        contexts: Dict[str, Any],
        states: Dict[str, Any],
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
    *, name: Optional[str] = None, registry: Optional[HooksRegistry] = None
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
    name: Optional[str] = None,
    registry: Optional[HooksRegistry] = None,
) -> TShutdown | Callable[[TShutdown], TShutdown]:
    """Decorator to register a shutdown hook"""


# --- Implementation ---
def shutdown(
    *args: TShutdown,
    name: Optional[str] = None,
    registry: Optional[HooksRegistry] = None,
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
