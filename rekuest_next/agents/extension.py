"""The base class for all agent extensions."""

from typing import List, runtime_checkable, Protocol, Optional
from rekuest_next.actors.types import Actor
from typing import TYPE_CHECKING
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from rekuest_next.agents.base import BaseAgent
    from rekuest_next.api.schema import ImplementationInput


@runtime_checkable
class AgentExtension(Protocol):
    """Protocol for all agent extensions."""

    cleanup: bool = False

    async def astart(self, instance_id: str) -> None:
        """This should be called when the agent starts"""
        ...

    def get_name(self) -> str:
        """Get the name of the extension. This is used to identify the extension
        in the registry."""
        return "default"

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
