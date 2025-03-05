from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import wraps
from typing import Dict, Any, Optional, Protocol, runtime_checkable
from pydantic import BaseModel, ConfigDict, Field
import asyncio

from koil.helpers import run_spawned
from rekuest_next.agents.context import (
    get_context_name,
    is_context,
    prepare_context_variables,
)
from rekuest_next.state.predicate import get_state_name, is_state
from rekuest_next.state.state import prepare_state_variables
from rekuest_next.utils import ensure_return_as_list
from .errors import StartupHookError, StateRequirementsNotMet
import inspect


@runtime_checkable
class BackgroundTask(Protocol):
    def __init__(self):
        pass

    async def arun(self, contexts: Dict[str, Any], proxies: Dict[str, Any]): ...


@dataclass
class StartupHookReturns:
    states: Dict[str, Any]
    contexts: Dict[str, Any]


@runtime_checkable
class StartupHook(Protocol):
    def __init__(self):
        pass

    async def arun(self, instance_id: str) -> StartupHookReturns:
        """Should return a dictionary of state variables"""
        ...


class HooksRegistry(BaseModel):
    background_worker: Dict[str, BackgroundTask] = Field(default_factory=dict)
    startup_hooks: Dict[str, StartupHook] = Field(default_factory=dict)

    _background_tasks: Dict[str, asyncio.Task] = {}

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def cleanup(self):
        for task in self._background_tasks.values():
            task.cancel()

    def register_background(cls, name: str, task: BackgroundTask):
        cls.background_worker[name] = task

    def register_startup(cls, name: str, hook: StartupHook):
        cls.startup_hooks[name] = hook

    async def arun_startup(self, instance_id: str) -> StartupHookReturns:
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

    def reset(self):
        self.background_worker = {}
        self.startup_hooks = {}



default_registry = None


class WrappedStartupHook(StartupHook):
    def __init__(self, func):
        self.func = func

        # check if has context argument
        arguments = inspect.signature(func).parameters
        if len(arguments) != 1:
            raise StartupHookError(
                "Startup hook must have exactly one argument (instance_id) or no arguments"
            )

    async def arun(self, instance_id: str) -> Optional[Dict[str, Any]]:
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
    def __init__(self, func):
        self.func = func
        # check if has context argument
        arguments = inspect.signature(func).parameters

        self.state_variables, self.state_returns = prepare_state_variables(func)

        self.context_variables, self.context_returns = prepare_context_variables(func)

    async def arun(self, contexts: Dict[str, Any], proxies: Dict[str, Any]):
        kwargs = {}
        for key, value in self.context_variables.items():
            try:
                kwargs[key] = contexts[value]
            except KeyError as e:
                raise StateRequirementsNotMet(
                    f"Context requirements not met: {e}"
                ) from e

        for key, value in self.state_variables.items():
            try:
                kwargs[key] = proxies[value]
            except KeyError as e:
                raise StateRequirementsNotMet(f"State requirements not met: {e}") from e

        return await self.func(**kwargs)
    
    
class WrappedThreadedBackgroundTask(BackgroundTask):
    def __init__(self, func):
        self.func = func
        # check if has context argument
        arguments = inspect.signature(func).parameters

        self.state_variables, self.state_returns = prepare_state_variables(func)

        self.context_variables, self.context_returns = prepare_context_variables(func)
        self.thread_pool = ThreadPoolExecutor(1)

    async def arun(self, contexts: Dict[str, Any], proxies: Dict[str, Any]):
        kwargs = {}
        for key, value in self.context_variables.items():
            try:
                kwargs[key] = contexts[value]
            except KeyError as e:
                raise StateRequirementsNotMet(
                    f"Context requirements not met: {e}"
                ) from e

        for key, value in self.state_variables.items():
            try:
                kwargs[key] = proxies[value]
            except KeyError as e:
                raise StateRequirementsNotMet(f"State requirements not met: {e}") from e

        return await run_spawned(self.func, **kwargs, executor=self.thread_pool, pass_context=True)



def get_default_hook_registry() -> HooksRegistry:
    global default_registry
    if default_registry is None:
        default_registry = HooksRegistry()
    return default_registry


def background(
    *func, name: Optional[str] = None, registry: Optional[HooksRegistry] = None
):
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
        if asyncio.iscoroutinefunction(function) or inspect.isasyncgenfunction(
            function
        ):
            registry.register_background(name, WrappedBackgroundTask(function))
        else:
            registry.register_background(name, WrappedThreadedBackgroundTask(function))
            

        return function

    else:

        def real_decorator(function):
            nonlocal registry, name
            
            # Simple bypass for now
            @wraps(function)
            def wrapped_function(*args, **kwargs):
                return function(*args, **kwargs)

            name = name or function.__name__
            registry = registry or get_default_hook_registry()
            if asyncio.iscoroutinefunction(function) or inspect.isasyncgenfunction(
            function
            ):
                registry.register_background(name, WrappedBackgroundTask(function))
            else:
                registry.register_background(name, WrappedThreadedBackgroundTask(function))
            

            return wrapped_function

        return real_decorator


def startup(
    *func, name: Optional[str] = None, registry: Optional[HooksRegistry] = None
):
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
        assert asyncio.iscoroutinefunction(
            function
        ), "Startup hooks must be (currently) async"
        registry = registry or get_default_hook_registry()
        name = name or function.__name__

        registry.register_startup(name, WrappedStartupHook(function))

        return function

    else:

        def real_decorator(function):
            nonlocal registry, name
            assert asyncio.iscoroutinefunction(
                function
            ), "Startup hooks must be (currently) async"

            # Simple bypass for now
            @wraps(function)
            def wrapped_function(*args, **kwargs):
                return function(*args, **kwargs)

            registry = registry or get_default_hook_registry()
            name = name or function.__name__
            registry.register_startup(name, WrappedStartupHook(function))

            return wrapped_function

        return real_decorator
