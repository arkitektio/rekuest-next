import contextvars
from rekuest_next.api.schema import DefinitionInput, DefinitionFragment
from rekuest_next.definition.validate import auto_validate, hash_definition
from typing import Dict
from pydantic import Field
from koil.composition import KoiledModel
import json
from rekuest_next.actors.types import ActorBuilder
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.structures.default import get_default_structure_registry

current_definition_registry = contextvars.ContextVar(
    "current_definition_registry", default=None
)
GLOBAL_DEFINITION_REGISTRY = None


def get_default_definition_registry():
    global GLOBAL_DEFINITION_REGISTRY
    if GLOBAL_DEFINITION_REGISTRY is None:
        GLOBAL_DEFINITION_REGISTRY = DefinitionRegistry()
    return GLOBAL_DEFINITION_REGISTRY


def get_current_definition_registry(allow_global=True):
    return current_definition_registry.get(get_default_definition_registry())


class DefinitionRegistry(KoiledModel):
    definitions: Dict[str, DefinitionInput] = Field(default_factory=dict, exclude=True)
    actor_builders: Dict[str, ActorBuilder] = Field(default_factory=dict, exclude=True)
    structure_registry: Dict[str, StructureRegistry] = Field(
        default_factory=dict, exclude=True
    )
    copy_from_default: bool = False

    _token: contextvars.Token = None

    def has_definitions(self):
        return len(self.defined_nodes) > 0 or len(self.templated_nodes) > 0

    def reset(self):
        self.defined_nodes = []  # dict are queryparams for the node
        self.templated_nodes = []

    def register_at_interface(
        self,
        interface: str,
        definition: DefinitionInput,
        structure_registry: StructureRegistry,
        actorBuilder: ActorBuilder,
    ):  # New Node
        self.definitions[interface] = definition
        self.actor_builders[interface] = actorBuilder
        self.structure_registry[interface] = structure_registry

    def get_builder_for_interface(self, interface) -> ActorBuilder:
        return self.actor_builders[interface]

    def get_structure_registry_for_interface(self, interface) -> StructureRegistry:
        assert interface in self.actor_builders, "No structure_interface for interface"
        return self.structure_registry[interface]

    def get_definition_for_interface(self, interface) -> DefinitionInput:
        assert interface in self.definitions, "No definition for interface"
        return self.definitions[interface]

    async def __aenter__(self):
        self._token = current_definition_registry.set(self)
        return self

    def dump(self):
        return {
            "definitions": [
                json.loads(x[0].json(exclude_none=True, exclude_unset=True))
                for x in self.defined_nodes
            ]
        }

    async def __aexit__(self, *args, **kwargs):
        current_definition_registry.set(None)

    class Config:
        copy_on_model_validation = False
