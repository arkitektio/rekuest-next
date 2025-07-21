"""Default extension for rekuest-next."""

from pydantic import ConfigDict, Field, BaseModel
from rekuest_next.api.schema import ImplementationInput
from rekuest_next.definition.registry import (
    DefinitionRegistry,
    get_default_definition_registry,
)

from rekuest_next.actors.types import Actor
from typing import TYPE_CHECKING, List, Optional

from rekuest_next.agents.errors import ExtensionError
import asyncio
import logging


logger = logging.getLogger(__name__)


class DefaultExtensionError(ExtensionError):
    """Base class for all standard extension errors."""

    pass


if TYPE_CHECKING:
    from rekuest_next.agents.base import BaseAgent


class DefaultExtension(BaseModel):
    """The default extension.

    The default extension is an extensions that encapsulates
    every registered function.

    """

    definition_registry: DefinitionRegistry = Field(
        default_factory=get_default_definition_registry,
        description="A global registry of all registered function/actors for this extension and all its dependencies. Think @register",
    )

    cleanup: bool = True
    _state_lock: Optional[asyncio.Lock] = None
    _instance_id: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def get_name(self) -> str:
        """Get the name of the extension. This is used to identify the extension
        in the registry."""
        return "default"

    async def aget_implementations(self) -> List[ImplementationInput]:
        """Get the implementations for this extension. This
        will be called when the agent starts and will
        be used to register the implementations on the rekuest server

        the implementations in the registry.
        Returns:
            List[ImplementationInput]: The implementations for this extension.
        """
        return list(self.definition_registry.implementations.values())

    async def astart(self, instance_id: str) -> None:
        """This should be called when the agent starts"""

        self._instance_id = instance_id

        self._state_lock = asyncio.Lock()

    def should_cleanup_on_init(self) -> bool:
        """Should the extension cleanup its implementations?"""
        return True

    async def aspawn_actor_for_interface(
        self,
        agent: "BaseAgent",
        interface: str,
    ) -> Actor:
        """Spawns an Actor from a Provision. This function closely mimics the
        spawining protocol within an actor. But maps implementation"""

        try:
            actor_builder = self.definition_registry.get_builder_for_interface(interface)

        except KeyError:
            raise ExtensionError(
                f"No Actor Builder found for interface {interface} and no extensions specified"
            )

        return actor_builder(
            agent=agent,
        )

    async def atear_down(self) -> None:
        """Tear down the extension. This will be called when the agent stops."""
        pass
