from typing import runtime_checkable, Protocol, Optional
from rekuest_next.api.schema import TemplateFragment
from rekuest_next.actors.base import Actor, Passport, ActorTransport
from rekuest_next.messages import Provision
from typing import TYPE_CHECKING
from rekuest_next.definition.registry import DefinitionRegistry

if TYPE_CHECKING:
    from rekuest_next.agents.base import BaseAgent


@runtime_checkable
class AgentExtension(Protocol):
    async def aspawn_actor_from_template(
        self,
        template: TemplateFragment,
        passport: Passport,
        transport: ActorTransport,
        agent: "BaseAgent",
    ) -> Optional[Actor]:
        """This should create an actor from a template and return it.

        The actor should not be started!

        TODO: This should be asserted

        """
        ...

    async def aregister_definitions(
        self, definition_registry: DefinitionRegistry, instance_id: str
    ):
        ...
