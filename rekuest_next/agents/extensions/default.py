from pydantic import ConfigDict, Field, BaseModel
from rekuest_next.agents.hooks import HooksRegistry, get_default_hook_registry
from rekuest_next.definition.registry import (
    DefinitionRegistry,
    get_default_definition_registry,
)
from rekuest_next.api.schema import (
    Template,
    acreate_state_schema,
    StateSchema,
)
from rekuest_next.actors.base import Actor, Passport, ActorTransport
from typing import TYPE_CHECKING, Any, Dict, Optional

from rekuest_next.agents.errors import ExtensionError
from rekuest_next.state.proxies import StateProxy
from rekuest_next.state.registry import StateRegistry, get_default_state_registry
import jsonpatch
import asyncio



class DefaultExtensionError(ExtensionError):
    pass


if TYPE_CHECKING:
    from rekuest_next.agents.base import BaseAgent


class DefaultExtension(BaseModel):
    definition_registry: DefinitionRegistry = Field(
        default_factory=get_default_definition_registry
    )
    state_registry: StateRegistry = Field(default_factory=get_default_state_registry)
    hook_registry: HooksRegistry = Field(default_factory=get_default_hook_registry)
    proxies: Dict[str, StateProxy] = Field(default_factory=dict)
    contexts: Dict[str, Any] = Field(default_factory=dict)

    _current_states = {}
    _shrunk_states = {}
    _state_schemas: Dict[str, StateSchema] = {}
    _background_tasks = {}
    _state_lock: Optional[asyncio.Lock] = None
    _instance_id: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def get_name(self):
        return "default"
    
    def get_definition_registry(self):
        return self.definition_registry

    async def astart(self, instance_id):
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
        """Should the extension cleanup its templates?"""
        return True

    async def aregister_schemas(self):
        for name, state_schema in self.state_registry.state_schemas.items():
            self._state_schemas[name] = await acreate_state_schema(
                state_schema=state_schema
            )

    async def ainit_state(self, state_key: str, value: Any):
        from rekuest_next.api.schema import aset_state

        schema = self._state_schemas[state_key]
        """
        if not schema.validate(value):
            raise DefaultExtensionError(f"Value {value} does not match schema {schema}")
        """

        # Shrink the value to the schema

        shrunk_state = await self.state_registry.ashrink_state(
            state_key=state_key, state=value
        )
        state = await aset_state(
            state_schema=schema.id, value=shrunk_state, instance_id=self._instance_id
        )
        print("State initialized", state)

        self._current_states[state_key] = value
        self.proxies[state_key] = StateProxy(proxy_holder=self, state_key=state_key)

    async def aget_state(self, state_key: str, attribute: Any) -> Any:
        async with self._state_lock:
            return getattr(self._current_states[state_key], attribute)

    async def aset_state(self, state_key: str, attribute: Any, value: Any):
        from rekuest_next.api.schema import aupdate_state

        async with self._state_lock:
            schema = self._state_schemas[state_key]
            """
            if not schema.validate(value):
                raise DefaultExtensionError(f"Value {value} does not match schema {schema}")
            """
            print(f"Setting state {state_key} attribute {attribute} to {value}")

            old_shrunk_state = await self.state_registry.ashrink_state(
                state_key=state_key, state=self._current_states[state_key]
            )
            setattr(self._current_states[state_key], attribute, value)
            new_shunk_state = await self.state_registry.ashrink_state(
                state_key=state_key, state=self._current_states[state_key]
            )

            patch = jsonpatch.make_patch(old_shrunk_state, new_shunk_state)

            # Shrink the value to the schema
            state = await aupdate_state(
                state_schema=schema.id,
                patches=patch.patch,
                instance_id=self._instance_id,
            )
            print("State updated", self._current_states[state_key], state)

    async def arun_background(self):
        for name, worker in self.hook_registry.background_worker.items():
            task = asyncio.create_task(
                worker.arun(contexts=self.contexts, proxies=self.proxies)
            )
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

    async def aspawn_actor_from_template(
        self,
        template: Template,
        passport: Passport,
        transport: ActorTransport,
        collector: "Collector",
        agent: "BaseAgent",
    ) -> Optional[Actor]:
        """Spawns an Actor from a Provision. This function closely mimics the
        spawining protocol within an actor. But maps template"""

        try:
            actor_builder = self.definition_registry.get_builder_for_interface(
                template.interface
            )

        except KeyError:
            raise ExtensionError(
                f"No Actor Builder found for template {template.interface} and no extensions specified"
            )

        return actor_builder(
            passport=passport,
            transport=transport,
            collector=collector,
            agent=agent,
            contexts=self.contexts,
            proxies=self.proxies,
        )

    async def aretrieve_registry(self):
        return self.definition_registry

    async def atear_down(self):
        await self.astop_background()

