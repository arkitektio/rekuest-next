"""The base class for all agent extensions."""

from typing import Dict, List, runtime_checkable, Protocol, Optional
from rekuest_next.actors.types import Actor
from typing import TYPE_CHECKING, Any
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from rekuest_next.agents.base import BaseAgent
    from rekuest_next.api.schema import (
        ImplementationInput,
        StateSchemaInput,
        LockSchemaInput,
    )
    from rekuest_next.agents.hooks.registry import StartupHook, BackgroundTask


@runtime_checkable
class AgentExtension(Protocol):
    """Protocol for all agent extensions."""

    cleanup: bool = False

    async def astart(self, instance_id: str, app_context: Any) -> None:
        """This should be called when the agent starts"""
        ...

    def get_name(self) -> str:
        """Get the name of the extension. This is used to identify the extension
        in the registry."""
        return "default"

    def get_implementations(self) -> List["ImplementationInput"]:
        """Get the implementations for this extension (sync version).

        This is called when the agent starts and will be used to register
        the implementations on the rekuest server.

        Returns:
            List[ImplementationInput]: The implementations for this extension.
        """
        ...

    def get_state_schemas(self) -> Dict[str, "StateSchemaInput"]:
        """Get the state schemas for this extension.

        Returns:
            Dict[str, StateSchemaInput]: Map of interface to state schema.
        """
        ...

    def get_startup_hooks(self) -> Dict[str, "StartupHook"]:
        """Get the startup hooks for this extension.

        Returns:
            Dict[str, StartupHook]: Map of hook name to startup hook.
        """
        ...

    def get_background_workers(self) -> Dict[str, "BackgroundTask"]:
        """Get the background workers for this extension.

        Returns:
            Dict[str, BackgroundTask]: Map of worker name to background task.
        """
        ...

    def get_static_implementations(self) -> List["ImplementationInput"]:
        """Get the implementations that are preregistered with this extension.
        This will be used to register the implementations on the rekuest server
        when the agent starts.

        Returns:
            List[ImplementationInput]: The implementations for this extension.
        """
        ...

    def get_lock_schemas(self) -> Dict[str, "LockSchemaInput"]:
        """Get the lock schemas for this extension.

        Returns:
            Dict[str, LockSchemaInput]: Map of interface to lock schema.
        """
        ...

    async def aget_implementations(self) -> List["ImplementationInput"]:
        """Get the implementations for this extension. This
        will be called when the agent starts and will
        be used to register the implementations on the rekuest server

        the implementations in the registry.
        Returns:
            List[ImplementationInput]: The implementations for this extension.
        """
        ...

    async def aspawn_actor_for_interface(
        self,
        agent: "BaseAgent",
        interface: str,
    ) -> Actor:
        """This should create an actor from a implementation and return it.

        The actor should not be started!

        TODO: This should be asserted

        """
        ...

    async def atear_down(self) -> None:
        """This should be called when the agent is torn down"""
        ...


class BaseAgentExtension(ABC):
    """Base class for all agent extensions."""

    cleanup: bool = False

    @abstractmethod
    async def astart(self) -> None:
        """This should be called when the agent starts"""
        ...

    @abstractmethod
    def get_name(self) -> str:
        """This should return the name of the extension"""
        raise NotImplementedError("Implement this method")

    def get_implementations(self) -> List["ImplementationInput"]:
        """Get the implementations for this extension (sync version).

        Returns:
            List[ImplementationInput]: The implementations for this extension.
        """
        return []

    def get_state_schemas(self) -> Dict[str, "StateSchemaInput"]:
        """Get the state schemas for this extension.

        Returns:
            Dict[str, StateSchemaInput]: Map of interface to state schema.
        """
        return {}

    def get_startup_hooks(self) -> Dict[str, "StartupHook"]:
        """Get the startup hooks for this extension.

        Returns:
            Dict[str, StartupHook]: Map of hook name to startup hook.
        """
        return {}

    def get_background_workers(self) -> Dict[str, "BackgroundTask"]:
        """Get the background workers for this extension.

        Returns:
            Dict[str, BackgroundTask]: Map of worker name to background task.
        """
        return {}

    @abstractmethod
    async def aspawn_actor_for_interface(
        self,
        agent: "BaseAgent",
        interface: str,
    ) -> Optional[Actor]:
        """This should create an actor from a implementation and return it.

        The actor should not be started!
        """
        ...

    @abstractmethod
    async def aget_implementations(self) -> List["ImplementationInput"]:
        """This should register the definitions for the agent.

        This is called when the agent is started, for each extensions. Extensions
        should register their definitions here and merge them with the agent's
        definition registry.
        """
        ...

    @abstractmethod
    async def atear_down(self) -> None:
        """
        This should be called when the agent is torn down
        """
