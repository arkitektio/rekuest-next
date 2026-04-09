"""Hooks for the agent"""

from concurrent.futures import ThreadPoolExecutor
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
import asyncio

from koil.helpers import run_spawned
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
    BackgroundFunction,
    ThreadedBackgroundFunction,
    AsyncBackgroundFunction,
)
from rekuest_next.state.publish import direct_publishing
from rekuest_next.state.utils import prepare_appcontext, prepare_state_variables


class WithVariables:
    def __init__(self, func: Callable[..., Any]) -> None:
        self.func = func
        self.state_variables, self.state_returns = prepare_state_variables(func)
        self.app_context_variables, self.app_context_returns = prepare_appcontext(func)
        self.context_variables, self.context_returns = prepare_context_variables(func)

        # Check the arg length of the function and raise an error if it is more than the context and state variables
        total_args = (
            self.state_variables.count
            + self.context_variables.count
            + +self.app_context_variables.count
        )
        if len(inspect.signature(func).parameters) > total_args:
            incorrect_args = set(inspect.signature(func).parameters.keys()) - set(
                self.state_variables.variable_keys
                + list(self.context_variables.context_variables.keys())
                + list(self.app_context_variables.app_context_variables.keys())
            )

            raise ValueError(
                f"Background function {func.__name__} has more arguments than the context and state variables. "
                f"Expected at most {total_args} arguments, but got {len(inspect.signature(func).parameters)}."
                f"{incorrect_args} are not valid argument names."
            )

    def get_kwargs(
        self, contexts: Dict[str, Any], states: Dict[str, Any]
    ) -> Dict[str, Any]:
        kwargs = {}
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

        for key, value in self.app_context_variables.app_context_variables.items():
            try:
                kwargs[key] = contexts[value]
            except KeyError as e:
                raise StateRequirementsNotMet(
                    f"App context requirements not met: {e}"
                ) from e

        for key, value in self.state_variables.write_state_variables.items():
            try:
                kwargs[key] = states[value]
            except KeyError as e:
                raise StateRequirementsNotMet(
                    f"State requirements not met: {e}. Available are {list(states.keys())}"
                ) from e
        return kwargs


class WrappedBackgroundTask(WithVariables):
    """Background task that runs in the event loop"""

    def __init__(self, func: AsyncBackgroundFunction) -> None:
        """Initialize the background task
        Args:
            func (Callable): The function to run in the background async
        """
        super().__init__(func)

    async def arun(
        self, agent: Agent, contexts: Dict[str, Any], states: Dict[str, Any]
    ) -> None:
        """Run the background task in the event loop"""
        kwargs = self.get_kwargs(contexts, states)
        with direct_publishing(agent):
            return await self.func(**kwargs)


class WrappedThreadedBackgroundTask(WithVariables):
    """Background task that runs in a thread pool"""

    def __init__(self, func: ThreadedBackgroundFunction) -> None:
        """Initialize the background task
        Args:
            func (Callable): The function to run in the background
        """
        super().__init__(func)
        self.thread_pool = ThreadPoolExecutor(1)

    def run_with_publishing(self, agent: Agent, **kwargs: Any) -> None:
        with direct_publishing(agent):
            return self.func(**kwargs)

    async def arun(
        self, agent: Agent, contexts: Dict[str, Any], states: Dict[str, Any]
    ) -> None:
        """Run the background task in a thread pool"""
        kwargs = self.get_kwargs(contexts, states)
        return await run_spawned(
            self.run_with_publishing,
            agent,
            **kwargs,  # type: ignore[arg-type]
        )


TBackground = TypeVar("TBackground", bound=BackgroundFunction)


@overload
def background(*args: TBackground) -> TBackground: ...


@overload
def background(
    *, name: Optional[str] = None, registry: Optional[HooksRegistry] = None
) -> Callable[[TBackground], TBackground]: ...


@overload
def background(
    *args: TBackground,
    name: Optional[str] = None,
    registry: Optional[HooksRegistry] = None,
) -> TBackground | Callable[[TBackground], TBackground]: ...


def background(  # noqa: ANN201
    *args: TBackground,
    name: Optional[str] = None,
    registry: Optional[HooksRegistry] = None,
) -> TBackground | Callable[[TBackground], TBackground]:
    """
    Background tasks are functions that are run in the background
    as asyncio tasks. They are started when the agent starts up
    and stopped automatically when the agent shuts down.

    """

    if len(args) > 1:
        raise ValueError("You can only register one function at a time.")
    if len(args) == 1:
        function = args[0]
        registry = registry or get_default_hook_registry()
        name = name or function.__name__
        if asyncio.iscoroutinefunction(function):
            registry.register_background(name, WrappedBackgroundTask(function))
        else:
            assert inspect.isfunction(function) or inspect.ismethod(function), (
                "Function must be a async function or a sync function"
            )
            t = cast(ThreadedBackgroundFunction, function)
            registry.register_background(name, WrappedThreadedBackgroundTask(t))

        return function

    else:

        def real_decorator(function: BackgroundFunction):  # noqa: ANN202, F821
            nonlocal registry, name

            name = name or function.__name__
            registry = registry or get_default_hook_registry()
            if asyncio.iscoroutinefunction(function):
                registry.register_background(name, WrappedBackgroundTask(function))
            else:
                assert inspect.isfunction(function), (
                    "Function must be a async function or a sync function"
                )
                t = cast(ThreadedBackgroundFunction, function)

                registry.register_background(name, WrappedThreadedBackgroundTask(t))

            return function

        return real_decorator  # type: ignore[return-value]
