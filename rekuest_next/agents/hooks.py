from functools import wraps
from typing import List, Dict, Any, Optional, Protocol, runtime_checkable
from pydantic import BaseModel, Field
import asyncio
from .errors import StartupHookError
import inspect


@runtime_checkable
class BackgroundTask(Protocol):
    def __init__(self):
        pass

    async def arun(self, context: Dict[str, Any]): ...


@runtime_checkable
class StartupHook(Protocol):
    def __init__(self):
        pass

    async def arun(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Should return a dictionary of state variables"""
        ...


class HooksRegistry(BaseModel):
    background_worker: Dict[str, BackgroundTask] = Field(default_factory=dict)
    startup_hooks: Dict[str, StartupHook] = Field(default_factory=dict)

    _background_tasks: Dict[str, asyncio.Task] = {}

    def register_background(cls, name: str, task: BackgroundTask):
        assert name not in cls.background_worker, f"Name {name} already registered"
        cls.background_worker[name] = task

    def register_startup(cls, name: str, hook: StartupHook):
        assert name not in cls.startup_hooks, f"Name {name} already registered"
        cls.startup_hooks[name] = hook

    async def arun_startup(self, instance_id: str) -> Dict[str, Any]:
        context = {"instance_id": instance_id}
        for key, hook in self.startup_hooks.items():
            try:
                answer = await hook.arun(context)
                if answer is not None:
                    context.update(answer)
            except Exception as e:
                raise StartupHookError(f"Startup hook {key} failed") from e
        return context

    async def arun_background(self, context: Dict[str, Any]):
        for name, worker in self.background_worker.items():
            task = asyncio.create_task(worker.arun(context=context))
            task.add_done_callback(lambda x: self._background_tasks.pop(name))
            task.add_done_callback(lambda x: print(f"Worker {name} finished"))
            self._background_tasks[name] = task

    async def astop_background(self):
        for name, task in self._background_tasks.items():
            task.cancel()

        try:
            await asyncio.gather(
                *self._background_tasks.values(), return_exceptions=True
            )
        except asyncio.CancelledError:
            pass

    def reset(self):
        self.background_worker = {}
        self.startup_hooks = {}

    class Config:
        arbitrary_types_allowed = True


default_registry = None


class WrappedStartupHook(StartupHook):
    def __init__(self, func):
        self.func = func

    async def arun(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return await self.func(context)


class WrappedBackgroundTask(BackgroundTask):
    def __init__(self, func):
        self.func = func
        # check if has context argument
        arguments = inspect.signature(func).parameters
        if "context" not in arguments:
            self._do_not_pass_context = True
        else:
            self._do_not_pass_context = False

    async def arun(self, context: Dict[str, Any]):
        if self._do_not_pass_context:
            return await self.func()
        else:
            return await self.func(context)


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
        assert asyncio.iscoroutinefunction(
            function
        ), "Startup hooks must be (currently) async"
        registry = registry or get_default_hook_registry()
        name = name or function.__name__
        registry.register_background(name, WrappedBackgroundTask(function))

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

            name = name or function.__name__
            registry = registry or get_default_hook_registry()
            registry.register_background(name, WrappedBackgroundTask(function))

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
