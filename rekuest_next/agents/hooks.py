"""Hooks for the agent"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Dict, Any, Optional, Protocol, runtime_checkable
from pydantic import BaseModel, ConfigDict, Field
import asyncio

from koil.helpers import run_spawned
from rekuest_next.agents.context import (
    get_context_name,
    is_context,
    prepare_context_variables,
)
from rekuest_next.state.predicate import get_state_name, is_state
from rekuest_next.state.decorator import prepare_state_variables
from rekuest_next.remote import ensure_return_as_list
from .errors import StartupHookError, StateRequirementsNotMet
import inspect


@runtime_checkable
class BackgroundTask(Protocol):
    """Background task that runs in the background
    This task is used to run a function in the background
    It is run in the order they are registered.
    """

    def __init__(self) -> None:
        """Initialize the background task"""
        pass

    async def arun(self, contexts: Dict[str, Any], proxies: Dict[str, Any]) -> None:
        """Run the background task in the event loop
        Args:
            contexts (Dict[str, Any]): The contexts of the agent
            proxies (Dict[str, Any]): The state variables of the agent
        Returns:
            None
        """
        ...


@dataclass
class StartupHookReturns:
    """Startup hook returns
    This is the return type of the startup hook.
    It contains the state variables and contexts that are used by the agent.
    """

    states: Dict[str, Any]
    contexts: Dict[str, Any]


@runtime_checkable
class StartupHook(Protocol):
    """Startup hook that runs when the agent starts up.
    This hook is used to setup the state variables and contexts that are used by the agent.
    It is run in the order they are registered.
    """

    def __init__(self) -> None:
        """Initialize the startup hook"""
        pass

    async def arun(self, instance_id: str) -> StartupHookReturns:
        """Should return a dictionary of state variables"""
        ...


class HooksRegistry(BaseModel):
    """Hook Registry

    Hooks are functions that are run when the default extension starts up.
    They can setup the state variables and contexts that are used by the agent.
    They are run in the order they are registered.

    """

    background_worker: Dict[str, BackgroundTask] = Field(default_factory=dict)
    startup_hooks: Dict[str, StartupHook] = Field(default_factory=dict)

    _background_tasks: Dict[str, asyncio.Task] = {}

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def cleanup(self) -> None:
        """Cleanup the registry"""
        for task in self._background_tasks.values():
            task.cancel()

    def register_background(self, name: str, task: BackgroundTask) -> None:
        """Register a background task in the registry."""
        self.background_worker[name] = task

    def register_startup(self, name: str, hook: StartupHook) -> None:
        """Register a startup hook in the registry."""
        self.startup_hooks[name] = hook

    async def arun_startup(self, instance_id: str) -> StartupHookReturns:
        """Run the startup hooks in the registry.

        Args:
            instance_id (str): The instance id of the agent
        Returns:
            StartupHookReturns: The state variables and contexts
        """
        states = {}
        contexts = {}

        for key, hook in self.startup_hooks.items():
            try:
                answer = await hook.arun(instance_id)
                for i in answer.states:
                    if i in states:
                        raise StartupHookError(f"State {i} already defined")
                    states[i] = answer.states[i]

                for i in answer.contexts:
                    if i in contexts:
                        raise StartupHookError(f"Context {i} already defined")
                    contexts[i] = answer.contexts[i]

            except Exception as e:
                raise StartupHookError(f"Startup hook {key} failed") from e
        return StartupHookReturns(states=states, contexts=contexts)

    def reset(self) -> None:
        """Reset the registry"""
        self.background_worker = {}
        self.startup_hooks = {}


default_registry = None


class WrappedStartupHook(StartupHook):
    """Startup hook that runs in the event loop"""

    def __init__(self, func: Callable) -> None:
        """Initialize the startup hook

        Args:

            func (Callable): The function to run in the startup hook
        """
        self.func = func

        # check if has context argument
        arguments = inspect.signature(func).parameters
        if len(arguments) != 1:
            raise StartupHookError(
                "Startup hook must have exactly one argument (instance_id) or no arguments"
            )

    async def arun(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """Run the startup hook in the event loop
        Args:
            instance_id (str): The instance id of the agent
        Returns:
            Optional[Dict[str, Any]]: The state variables and contexts
        """
        parsed_returns = await self.func(instance_id)

        returns = ensure_return_as_list(parsed_returns)

        states = {}
        contexts = {}

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


class WrappedBackgroundTask(BackgroundTask):
    """Background task that runs in the event loop"""

    def __init__(self, func: Callable) -> None:
        """Initialize the background task
        Args:
            func (Callable): The function to run in the background async
        """
        self.func = func
        # check if has context argument
        inspect.signature(func).parameters

        self.state_variables, self.state_returns = prepare_state_variables(func)

        self.context_variables, self.context_returns = prepare_context_variables(func)

    async def arun(self, contexts: Dict[str, Any], proxies: Dict[str, Any]) -> None:
        """Run the background task in the event loop"""
        kwargs = {}
        for key, value in self.context_variables.items():
            try:
                kwargs[key] = contexts[value]
            except KeyError as e:
                raise StateRequirementsNotMet(f"Context requirements not met: {e}") from e

        for key, value in self.state_variables.items():
            try:
                kwargs[key] = proxies[value]
            except KeyError as e:
                raise StateRequirementsNotMet(f"State requirements not met: {e}") from e

        return await self.func(**kwargs)


class WrappedThreadedBackgroundTask(BackgroundTask):
    """Background task that runs in a thread pool"""

    def __init__(self, func: Callable) -> None:
        """Initialize the background task
        Args:
            func (Callable): The function to run in the background
        """
        self.func = func
        # check if has context argument
        inspect.signature(func).parameters

        self.state_variables, self.state_returns = prepare_state_variables(func)

        self.context_variables, self.context_returns = prepare_context_variables(func)
        self.thread_pool = ThreadPoolExecutor(1)

    async def arun(self, contexts: Dict[str, Any], proxies: Dict[str, Any]) -> None:
        """Run the background task in a thread pool"""
        kwargs = {}
        for key, value in self.context_variables.items():
            try:
                kwargs[key] = contexts[value]
            except KeyError as e:
                raise StateRequirementsNotMet(f"Context requirements not met: {e}") from e

        for key, value in self.state_variables.items():
            try:
                kwargs[key] = proxies[value]
            except KeyError as e:
                raise StateRequirementsNotMet(f"State requirements not met: {e}") from e

        return await run_spawned(self.func, **kwargs, executor=self.thread_pool, pass_context=True)


def get_default_hook_registry() -> HooksRegistry:
    """Get the default hook registry."""
    global default_registry
    if default_registry is None:
        default_registry = HooksRegistry()
    return default_registry


def background(  # noqa: ANN201
    *func: Callable, name: Optional[str] = None, registry: Optional[HooksRegistry] = None
) -> Callable:
    """
    Background tasks are functions that are run in the background
    as asyncio tasks. They are started when the agent starts up
    and stopped automatically when the agent shuts down.

    """

    if len(func) > 1:
        raise ValueError("You can only register one function at a time.")
    if len(func) == 1:
        function = func[0]
        registry = registry or get_default_hook_registry()
        name = name or function.__name__
        if asyncio.iscoroutinefunction(function) or inspect.isasyncgenfunction(function):
            registry.register_background(name, WrappedBackgroundTask(function))
        else:
            registry.register_background(name, WrappedThreadedBackgroundTask(function))

        return function

    else:

        def real_decorator(function: Callable):  # noqa: ANN202, F821
            nonlocal registry, name

            # Simple bypass for now
            @wraps(function)
            def wrapped_function(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
                return function(*args, **kwargs)

            name = name or function.__name__
            registry = registry or get_default_hook_registry()
            if asyncio.iscoroutinefunction(function) or inspect.isasyncgenfunction(function):
                registry.register_background(name, WrappedBackgroundTask(function))
            else:
                registry.register_background(name, WrappedThreadedBackgroundTask(function))

            return wrapped_function

        return real_decorator


def startup(
    *func: Callable, name: Optional[str] = None, registry: Optional[HooksRegistry] = None
) -> Callable:
    """
    This is a decorator that registers a function as a startup hook.
    Startup hooks are called when the agent starts up and AFTER the
    definitions have been registered with the agent.

    Then, the startup hook is called and the state variables are
    returned as a dictionary. These state variables are then passed
    accessible in every actors' context.
    """
    if len(func) > 1:
        raise ValueError("You can only register one function at a time.")
    if len(func) == 1:
        function = func[0]
        assert asyncio.iscoroutinefunction(function), "Startup hooks must be (currently) async"
        registry = registry or get_default_hook_registry()
        name = name or function.__name__

        registry.register_startup(name, WrappedStartupHook(function))

        return function

    else:

        def real_decorator(function: Callable):  # noqa: ANN202, F821
            nonlocal registry, name
            assert asyncio.iscoroutinefunction(function), "Startup hooks must be (currently) async"

            # Simple bypass for now
            @wraps(function)
            def wrapped_function(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
                return function(*args, **kwargs)

            registry = registry or get_default_hook_registry()
            name = name or function.__name__
            registry.register_startup(name, WrappedStartupHook(function))

            return wrapped_function

        return real_decorator
