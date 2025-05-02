"""Registry for definitions."""

import contextvars
from rekuest_next.api.schema import (
    DefinitionInput,
    TemplateInput,
    CreateTemplateInput,
)
from typing import Dict
from pydantic import BaseModel, ConfigDict, Field
import json
from rekuest_next.actors.types import ActorBuilder
from rekuest_next.structures.registry import StructureRegistry
import hashlib

from rekuest_next.structures.types import JSONSerializable


current_definition_registry = contextvars.ContextVar("current_definition_registry", default=None)


class DefinitionRegistry(BaseModel):
    """A registry of definitions.

    This registry is used to store the definitions of all the functions and generators
    that are registered in the system. It is used to create the actor builders and
    structure registries for each function and generator.
    """

    templates: Dict[str, TemplateInput] = Field(default_factory=dict, exclude=True)
    actor_builders: Dict[str, ActorBuilder] = Field(default_factory=dict, exclude=True)
    structure_registries: Dict[str, StructureRegistry] = Field(default_factory=dict, exclude=True)
    copy_from_default: bool = False
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    def register_at_interface(
        self,
        interface: str,
        template: TemplateInput,
        actorBuilder: ActorBuilder,
    ) -> None:
        """Register a function or generator at the given interface."""
        self.templates[interface] = template
        self.actor_builders[interface] = actorBuilder

    def get_builder_for_interface(self, interface: str) -> ActorBuilder:
        """Get the actor builder for a given interface."""
        return self.actor_builders[interface]

    def get_definition_for_interface(self, interface: str) -> DefinitionInput:
        """Get the definition for a given interface."""
        assert interface in self.templates, "No definition for interface"
        return self.templates[interface].definition

    def get_template_input_for_interface(self, interface: str) -> CreateTemplateInput:
        """Get the template input for a given interface."""
        assert interface in self.templates, "No definition for interface"
        return self.templates[interface]

    def dump(self) -> Dict[str, Dict[str, JSONSerializable]]:
        """Dump the registry to a JSON serializable format."""
        return {
            "templates": [
                json.loads(x[0].json(exclude_none=True, exclude_unset=True)) for x in self.templates
            ]
        }

    def hash(self) -> str:
        """Get the hash of the registry."""
        return hashlib.sha256(json.dumps(self.dump(), sort_keys=True).encode()).hexdigest()

    def create_merged(
        self, other: "DefinitionRegistry", strict: bool = True
    ) -> "DefinitionRegistry":
        """Create a new registry that is a merge of this one and another one."""
        new = DefinitionRegistry()

        for key in self.templates:
            if strict:
                assert key in other.templates, (
                    f"Cannot merge definition registrs with the same interface in strict mode: {key}"
                )
            new.templates[key] = self.templates[key]
            new.actor_builders[key] = self.actor_builders[key]
            new.structure_registries[key] = self.structure_registries[key]

        return new

    def merge_with(self, other: "DefinitionRegistry", strict: bool = True) -> None:
        """Merge this registry with another one.

        Args:
            other (DefinitionRegistry): The other registry to merge with.
            strict (bool): If True, raise an error if the same interface is found in both registries.


        Raises:
            AssertionError: If strict is True and the same interface is found in both registries.
        """
        for key in other.templates:
            if strict:
                assert key not in self.templates, (
                    f"Cannot merge definition registrs with the same interface in strict mode: {key}"
                )
            self.templates[key] = other.templates[key]
            self.actor_builders[key] = other.actor_builders[key]
            self.structure_registries[key] = other.structure_registries[key]


GLOBAL_DEFINITION_REGISTRY = None


def get_default_definition_registry() -> DefinitionRegistry:
    """Get the default definition registry.

    Returns:
        DefinitionRegistry: The default definition registry.
    """
    global GLOBAL_DEFINITION_REGISTRY
    if GLOBAL_DEFINITION_REGISTRY is None:
        GLOBAL_DEFINITION_REGISTRY = DefinitionRegistry()
    return GLOBAL_DEFINITION_REGISTRY
