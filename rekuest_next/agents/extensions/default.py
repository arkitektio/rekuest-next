"""Default extension for rekuest-next."""

from pydantic import ConfigDict, Field, BaseModel, PrivateAttr
from rekuest_next.agents.hooks.registry import HooksRegistry, get_default_hook_registry
from rekuest_next.definition.registry import (
    DefinitionRegistry,
    get_default_definition_registry,
)
from rekuest_next.api.schema import (
    ImplementationInput,
    acreate_state_schema,
    StateSchema,
)
from rekuest_next.actors.types import Actor
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from rekuest_next.agents.errors import ExtensionError
from rekuest_next.state.proxies import StateProxy
from rekuest_next.state.registry import StateRegistry, get_default_state_registry
import jsonpatch  # type: ignore
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
    state_registry: StateRegistry = Field(
        default_factory=get_default_state_registry,
        description="A global registry of all registered states for this extension. Think @state",
    )
    hook_registry: HooksRegistry = Field(
        default_factory=get_default_hook_registry,
        description="The hooks registry for this extension. Think @startup and @background",
    )
    proxies: Dict[str, StateProxy] = Field(default_factory=dict)
    contexts: Dict[str, Any] = Field(default_factory=dict)
    cleanup: bool = True

    _current_states: Dict[str, Any] = PrivateAttr(default_factory=dict)
    _shrunk_states: Dict[str, Any] = PrivateAttr(default_factory=dict)
    _state_schemas: Dict[str, StateSchema] = {}
    _background_tasks: Dict[str, asyncio.Task[None]] = PrivateAttr(default_factory=dict)
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

        await self.aregister_schemas()

        self._instance_id = instance_id

        self._state_lock = asyncio.Lock()

        hook_return = await self.hook_registry.arun_startup(instance_id)

        for state_key, state_value in hook_return.states.items():
            await self.ainit_state(state_key, state_value)

        for context_key, context_value in hook_return.contexts.items():
            self.contexts[context_key] = context_value

        await self.arun_background()

    def should_cleanup_on_init(self) -> bool:
        """Should the extension cleanup its implementations?"""
        return True

    async def aregister_schemas(self) -> None:
        """Register the schemas for this extension. This will be called when
        the agent starts and will be used to register the schemas on the
        rekuest server."""
        for name, state_schema in self.state_registry.state_schemas.items():
            self._state_schemas[name] = await acreate_state_schema(
                state_schema=state_schema
            )

    async def ainit_state(self, state_key: str, value: Any) -> None:  # noqa: ANN401
        """Initialize the state of the extension. This will be called when"""
        from rekuest_next.api.schema import aset_state

        if not self._instance_id:
            raise DefaultExtensionError(
                "Instance ID is not set. This extensions is not initialized"
            )

        schema = self._state_schemas[state_key]
        """
        if not schema.validate(value):
            raise DefaultExtensionError(f"Value {value} does not match schema {schema}")
        """

        # Shrink the value to the schema

        shrunk_state = await self.state_registry.ashrink_state(
            state_key=state_key, state=value
        )
        await aset_state(
            state_schema=schema.id, value=shrunk_state, instance_id=self._instance_id
        )

        self._current_states[state_key] = value
        self.proxies[state_key] = StateProxy(proxy_holder=self, state_key=state_key)

    async def aget_state(self, state_key: str, attribute: Any) -> Any:  # noqa: ANN401
        """Get the state of the extension. This will be called when"""
        if not self._state_lock:
            raise DefaultExtensionError(
                "State lock is not set. This extensions is not initialized"
            )

        async with self._state_lock:
            return getattr(self._current_states[state_key], attribute)

    async def aset_state(self, state_key: str, attribute: Any, value: Any) -> None:  # noqa: ANN401
        """Set the state of the extension. This will be called when the agent starts"""
        from rekuest_next.api.schema import aupdate_state

        if not self._state_lock:
            raise DefaultExtensionError(
                "State lock is not set. This extensions is not initialized"
            )

        async with self._state_lock:
            schema = self._state_schemas[state_key]
            """
            if not schema.validate(value):
                raise DefaultExtensionError(f"Value {value} does not match schema {schema}")
            """
            logger.debug(f"Setting state {state_key} attribute {attribute} to {value}")

            old_shrunk_state = await self.state_registry.ashrink_state(
                state_key=state_key, state=self._current_states[state_key]
            )
            setattr(self._current_states[state_key], attribute, value)
            new_shunk_state = await self.state_registry.ashrink_state(
                state_key=state_key, state=self._current_states[state_key]
            )

            patch = jsonpatch.make_patch(old_shrunk_state, new_shunk_state)  # type: ignore

            # Shrink the value to the schema
            state = await aupdate_state(
                state_schema=schema.id,
                patches=patch.patch,  # type: ignore
                instance_id=self._instance_id,  # type: ignore
            )
            print("State updated", self._current_states[state_key], state)

    async def arun_background(self) -> None:
        """Run the background tasks. This will be called when the agent starts."""
        for name, worker in self.hook_registry.background_worker.items():
            task = asyncio.create_task(
                worker.arun(contexts=self.contexts, proxies=self.proxies)
            )
            task.add_done_callback(lambda x: self._background_tasks.pop(name))
            task.add_done_callback(lambda x: print(f"Worker {name} finished"))
            self._background_tasks[name] = task

    async def astop_background(self) -> None:
        """Stop the background tasks. This will be called when the agent stops."""
        for _, task in self._background_tasks.items():
            task.cancel()

        try:
            await asyncio.gather(
                *self._background_tasks.values(), return_exceptions=True
            )
        except asyncio.CancelledError:
            pass

    async def aspawn_actor_for_interface(
        self,
        agent: "BaseAgent",
        interface: str,
    ) -> Actor:
        """Spawns an Actor from a Provision. This function closely mimics the
        spawining protocol within an actor. But maps implementation"""

        try:
            actor_builder = self.definition_registry.get_builder_for_interface(
                interface
            )

        except KeyError:
            raise ExtensionError(
                f"No Actor Builder found for interface {interface} and no extensions specified"
            )

        return actor_builder(
            agent=agent,
            contexts=self.contexts,
            proxies=self.proxies,
        )

    async def atear_down(self) -> None:
        """Tear down the extension. This will be called when the agent stops."""
        await self.astop_background()
