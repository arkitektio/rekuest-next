"""Hooks for the agent"""

from dataclasses import dataclass
from typing import (
    Dict,
    Any,
    Protocol,
    runtime_checkable,
)
from pydantic import BaseModel, ConfigDict, Field


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

    async def arun(self, instance_id: str, app_context: Any) -> StartupHookReturns:
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

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def register_background(self, name: str, task: BackgroundTask) -> None:
        """Register a background task in the registry."""
        self.background_worker[name] = task

    def register_startup(self, name: str, hook: StartupHook) -> None:
        """Register a startup hook in the registry."""
        self.startup_hooks[name] = hook

    def reset(self) -> None:
        """Reset the registry"""
        self.background_worker = {}
        self.startup_hooks = {}


def get_default_hook_registry() -> HooksRegistry:
    """Return the default hook registry (the app registry's).

    Returns:
        HooksRegistry: The hooks registry of the global app registry.
    """
    from rekuest_next.app import get_default_app_registry

    return get_default_app_registry().hooks_registry
