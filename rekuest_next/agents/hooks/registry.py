"""Hooks for the agent"""

from dataclasses import dataclass
from typing import (
    Dict,
    Any,
    Protocol,
    runtime_checkable,
)
from pydantic import BaseModel, ConfigDict, Field
import asyncio

from .errors import StartupHookError


@runtime_checkable
class BackgroundTask(Protocol):
    """Background task that runs in the background
    This task is used to run a function in the background
    It is run in the order they are registered.
    """

    def __init__(self) -> None:
        """Initialize the background task"""
        pass

    async def arun(self, contexts: Dict[str, Any], states: Dict[str, Any]) -> None:
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

    _background_tasks: Dict[str, asyncio.Task[None]] = {}
    startup_timeout: float | None = 20
    """Timeout for the startup hooks, if None, no timeout is set"""

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
        states: Dict[str, Any] = {}
        contexts: Dict[str, Any] = {}

        for key, hook in self.startup_hooks.items():
            try:
                answer = (
                    await asyncio.wait_for(hook.arun(instance_id), timeout=self.startup_timeout)
                    if self.startup_timeout
                    else await hook.arun(instance_id)
                )
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


def get_default_hook_registry() -> HooksRegistry:
    """Get the default hook registry
    This is used to register hooks and background tasks
    """
    global default_registry
    if default_registry is None:
        default_registry = HooksRegistry()
    return default_registry
