from pydantic import Field, BaseModel
from rekuest_next.definition.registry import (
    DefinitionRegistry,
    get_default_definition_registry,
)
from rekuest_next.api.schema import TemplateFragment
from rekuest_next.actors.base import Actor, Passport, ActorTransport
from typing import TYPE_CHECKING, Optional

from rekuest_next.agents.errors import ExtensionError


class DefaultExtensionError(ExtensionError):
    pass


if TYPE_CHECKING:
    from rekuest_next.agents.base import BaseAgent


class DefaultExtension(BaseModel):
    definition_registry: DefinitionRegistry = Field(
        default_factory=get_default_definition_registry
    )

    async def should_cleanup_on_init(self) -> bool:
        """Should the extension cleanup its templates?"""
        return True

    async def aspawn_actor_from_template(
        self,
        template: TemplateFragment,
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

        except KeyError as e:
            raise ExtensionError(
                f"No Actor Builder found for template {template.interface} and no extensions specified"
            )

        return actor_builder(
            passport=passport,
            transport=transport,
            collector=collector,
            agent=agent,
        )

    async def aretrieve_registry(self):
        return self.definition_registry
