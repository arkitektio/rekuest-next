import contextvars
from rekuest_next.api.schema import (
    DefinitionInput,
    TemplateInput,
    CreateTemplateInput,
)
from typing import Dict, Union
from pydantic import Field
from koil.composition import KoiledModel
import json
from rekuest_next.actors.types import ActorBuilder
from rekuest_next.structures.registry import StructureRegistry
import hashlib


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
    templates: Dict[str, TemplateInput] = Field(default_factory=dict, exclude=True)
    actor_builders: Dict[str, ActorBuilder] = Field(default_factory=dict, exclude=True)
    structure_registries: Dict[str, StructureRegistry] = Field(
        default_factory=dict, exclude=True
    )
    copy_from_default: bool = False

    _token: Union[contextvars.Token, None] = None

    def register_at_interface(
        self,
        interface: str,
        template: TemplateInput,
        structure_registry: StructureRegistry,
        actorBuilder: ActorBuilder,
    ):  # New Node
        self.templates[interface] = template
        self.actor_builders[interface] = actorBuilder
        self.structure_registries[interface] = structure_registry

    def get_builder_for_interface(self, interface) -> ActorBuilder:
        return self.actor_builders[interface]

    def get_structure_registry_for_interface(self, interface) -> StructureRegistry:
        assert interface in self.actor_builders, "No structure_interface for interface"
        return self.structure_registries[interface]

    def get_definition_for_interface(self, interface) -> DefinitionInput:
        assert interface in self.templates, "No definition for interface"
        return self.templates[interface].definition

    def get_template_input_for_interface(self, interface) -> CreateTemplateInput:
        assert interface in self.templates, "No definition for interface"
        return self.templates[interface]

    async def __aenter__(self):
        self._token = current_definition_registry.set(self)
        return self

    def dump(self):
        return {
            "templates": [
                json.loads(x[0].json(exclude_none=True, exclude_unset=True))
                for x in self.templates
            ]
        }

    def hash(self):
        return hashlib.sha256(
            json.dumps(self.dump(), sort_keys=True).encode()
        ).hexdigest()

    async def __aexit__(self, *args, **kwargs):
        current_definition_registry.set(None)

    def create_merged(self, other: "DefinitionRegistry", strict=True):
        new = DefinitionRegistry()

        for key in self.templates:
            if strict:
                assert (
                    key in other.templates
                ), f"Cannot merge definition registrs with the same interface in strict mode: {key}"
            new.templates[key] = self.templates[key]
            new.actor_builders[key] = self.actor_builders[key]
            new.structure_registries[key] = self.structure_registries[key]

        return new

    def merge_with(self, other: "DefinitionRegistry", strict=True):
        for key in other.templates:
            if strict:
                assert (
                    key not in self.templates
                ), f"Cannot merge definition registrs with the same interface in strict mode: {key}"
            self.templates[key] = other.templates[key]
            self.actor_builders[key] = other.actor_builders[key]
            self.structure_registries[key] = other.structure_registries[key]
