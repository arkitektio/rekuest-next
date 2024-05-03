import contextvars
from rekuest_next.api.schema import DefinitionInput, DefinitionFragment, DependencyInput
from rekuest_next.definition.validate import auto_validate, hash_definition
from typing import Dict, List
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
    dependencies: Dict[str, DependencyInput] = Field(default_factory=dict, exclude=True)
    actor_builders: Dict[str, ActorBuilder] = Field(default_factory=dict, exclude=True)
    structure_registries: Dict[str, StructureRegistry] = Field(
        default_factory=dict, exclude=True
    )
    copy_from_default: bool = False

    _token: contextvars.Token = None

    def register_at_interface(
        self,
        interface: str,
        definition: DefinitionInput,
        structure_registry: StructureRegistry,
        actorBuilder: ActorBuilder,
        dependencies: Dict[str, str] = None,
    ):  # New Node
        self.definitions[interface] = definition
        self.actor_builders[interface] = actorBuilder
        self.structure_registries[interface] = structure_registry
        self.dependencies[interface] = dependencies

    def get_builder_for_interface(self, interface) -> ActorBuilder:
        return self.actor_builders[interface]

    def get_structure_registry_for_interface(self, interface) -> StructureRegistry:
        assert interface in self.actor_builders, "No structure_interface for interface"
        return self.structure_registries[interface]

    def get_definition_for_interface(self, interface) -> DefinitionInput:
        assert interface in self.definitions, "No definition for interface"
        return self.definitions[interface]

    def get_dependencies_for_interface(self, interface) -> List[DependencyInput]:
        assert interface in self.dependencies, "No dependencies for interface"
        return self.dependencies[interface]

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

    def create_merged(self, other, strict=True):
        new = DefinitionRegistry()

        for key in self.definitions:
            if strict:
                assert (
                    key in other.definitions
                ), f"Cannot merge definition registrs with the same interface in strict mode: {key}"
            new.definitions[key] = self.definitions[key]
            new.dependencies[key] = self.dependencies[key]
            new.actor_builders[key] = self.actor_builders[key]
            new.structure_registries[key] = self.structure_registries[key]

        return new

    def merge_with(self, other, strict=True):
        for key in other.definitions:
            if strict:
                assert (
                    key not in self.definitions
                ), f"Cannot merge definition registrs with the same interface in strict mode: {key}"
            self.definitions[key] = other.definitions[key]
            self.dependencies[key] = other.dependencies[key]
            self.actor_builders[key] = other.actor_builders[key]
            self.structure_registries[key] = other.structure_registries[key]

    class Config:
        copy_on_model_validation = False
