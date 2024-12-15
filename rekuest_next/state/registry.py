import contextvars

from rekuest_next.api.schema import (
    CreateTemplateInput,
    StateSchemaInput,
)
from typing import Any, Dict
from pydantic import Field
from koil.composition import KoiledModel
import json
from rekuest_next.actors.types import ActorBuilder
from rekuest_next.structures.registry import StructureRegistry
import hashlib

from rekuest_next.structures.serialization.actor import ashrink_return


current_state_registry = contextvars.ContextVar(
    "current_definition_registry", default=None
)
GLOBAL_STATE_REGISTRY = None


def get_default_state_registry():
    global GLOBAL_STATE_REGISTRY
    if GLOBAL_STATE_REGISTRY is None:
        GLOBAL_STATE_REGISTRY = StateRegistry()
    return GLOBAL_STATE_REGISTRY


def get_current_state_registry(allow_global=True):
    return current_state_registry.get(get_default_state_registry())


class StateRegistry(KoiledModel):
    state_schemas: Dict[str, StateSchemaInput] = Field(
        default_factory=dict, exclude=True
    )
    registry_schemas: Dict[str, StructureRegistry] = Field(
        default_factory=dict, exclude=True
    )

    def register_at_name(
        self, name: str, state_schema: StateSchemaInput, registry: StructureRegistry
    ):  # New Node
        self.state_schemas[name] = state_schema
        self.registry_schemas[name] = registry

    def get_builder_for_interface(self, interface) -> ActorBuilder:
        return self.actor_builders[interface]

    def get_structure_registry_for_interface(self, interface) -> StructureRegistry:
        return self.registry_schemas[interface]

    def get_schema_for_name(self, name) -> StateSchemaInput:
        assert name in self.state_schemas, "No definition for interface"
        return self.state_schemas[name]

    def get_template_input_for_interface(self, interface) -> CreateTemplateInput:
        assert interface in self.templates, "No definition for interface"
        return self.templates[interface]

    async def __aenter__(self):
        self._token = current_state_registry.set(self)
        return self

    async def __aexit__(self, *args, **kwargs):
        current_state_registry.reset(self._token)
        self._token = None
        return

    async def ashrink_state(self, state_key, state) -> Dict[str, Any]:
        shrinked = {}
        for port in self.state_schemas[state_key].ports:
            shrinked[port.key] = await ashrink_return(
                port, getattr(state, port.key), self.registry_schemas[state_key]
            )

        return shrinked

    def dump(self):
        return {
            "state_schemas": [
                json.loads(x[0].json(exclude_none=True, exclude_unset=True))
                for x in self.templates
            ]
        }

    def hash(self):
        return hashlib.sha256(
            json.dumps(self.dump(), sort_keys=True).encode()
        ).hexdigest()
