"""Default extension for rekuest-next."""

from pydantic import ConfigDict, Field, BaseModel
from rekuest_next.api.schema import (
    ImplementationInput,
    LockSchemaInput,
    StateSchemaInput,
)
from rekuest_next.app import AppRegistry, get_default_app_registry

from rekuest_next.actors.types import Actor
from typing import TYPE_CHECKING, Dict, List, Optional, Any

from rekuest_next.agents.errors import ExtensionError
from rekuest_next.agents.hooks.registry import StartupHook, BackgroundTask
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

    app_registry: AppRegistry = Field(
        default_factory=get_default_app_registry,
        description="The unified app registry containing all registries for this extension.",
    )

    cleanup: bool = True
    _state_lock: Optional[asyncio.Lock] = None
    _instance_id: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def get_name(self) -> str:
        """Get the name of the extension. This is used to identify the extension
        in the registry."""
        return "default"

    def get_implementations(self) -> List[ImplementationInput]:
        """Get the implementations for this extension (sync version).

        Returns:
            List[ImplementationInput]: The implementations for this extension.
        """
        return list(self.app_registry.implementation_registry.implementations.values())

    def get_static_implementations(self) -> List[ImplementationInput]:
        """Get the implementations that are preregistered with this extension.
        This will be used to register the implementations on the rekuest server
        when the agent starts.

        Returns:
            List[ImplementationInput]: The implementations for this extension.
        """
        return list(self.app_registry.implementation_registry.implementations.values())

    def get_state_schemas(self) -> Dict[str, StateSchemaInput]:
        """Get the state schemas for this extension.

        Returns:
            Dict[str, StateSchemaInput]: Map of interface to state schema.
        """
        return dict(self.app_registry.state_registry.state_schemas)

    def get_lock_schemas(self) -> Dict[str, LockSchemaInput]:
        """Get the lock schemas for this extension.

        Returns:
            Dict[str, LockSchemaInput]: Map of interface to lock schema.
        """

        schemas: Dict[str, LockSchemaInput] = {}

        for (
            interface,
            schema,
        ) in self.app_registry.implementation_registry.implementations.items():
            logger.debug(f"Lock schema for interface {interface}: {schema}")

            if schema.locks is not None:
                for lock in schema.locks:
                    if lock not in schemas:
                        schemas[lock] = LockSchemaInput(
                            key=lock,
                            description=f"Lock schema for {lock}",
                        )

        return schemas

    def get_startup_hooks(self) -> Dict[str, StartupHook]:
        """Get the startup hooks for this extension.

        Returns:
            Dict[str, StartupHook]: Map of hook name to startup hook.
        """
        return dict(self.app_registry.hooks_registry.startup_hooks)

    def get_background_workers(self) -> Dict[str, BackgroundTask]:
        """Get the background workers for this extension.

        Returns:
            Dict[str, BackgroundTask]: Map of worker name to background task.
        """
        return dict(self.app_registry.hooks_registry.background_worker)

    async def aget_implementations(self) -> List[ImplementationInput]:
        """Get the implementations for this extension. This
        will be called when the agent starts and will
        be used to register the implementations on the rekuest server

        the implementations in the registry.
        Returns:
            List[ImplementationInput]: The implementations for this extension.
        """
        return list(self.app_registry.implementation_registry.implementations.values())

    async def astart(self, instance_id: str, app_context: Any) -> None:
        """This should be called when the agent starts"""

        self._instance_id = instance_id
        self._state_lock = asyncio.Lock()
        self._app_context = app_context

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
            actor_builder = self.app_registry.implementation_registry.get_builder_for_interface(
                interface
            )

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
