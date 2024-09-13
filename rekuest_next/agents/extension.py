from typing import runtime_checkable, Protocol, Optional
from rekuest_next.api.schema import TemplateFragment
from rekuest_next.actors.base import Actor, Passport, ActorTransport
from typing import TYPE_CHECKING
from rekuest_next.definition.registry import DefinitionRegistry
from rekuest_next.collection.collector import Collector

if TYPE_CHECKING:
    from rekuest_next.agents.base import BaseAgent


@runtime_checkable
class AgentExtension(Protocol):
    async def astart(self):
        """This should be called when the agent starts"""
        ...

    async def should_cleanup_on_init(self) -> bool:
        """Should the extension cleanup its templates?"""
        ...

    async def get_name(self) -> str:
        """This should return the name of the extension"""
        raise NotImplementedError("Implement this method")

    async def aspawn_actor_from_template(
        self,
        template: TemplateFragment,
        passport: Passport,
        transport: ActorTransport,
        agent: "BaseAgent",
        collector: "Collector",
    ) -> Optional[Actor]:
        """This should create an actor from a template and return it.

        The actor should not be started!

        TODO: This should be asserted

        """
        ...

    async def aretrieve_registry(
        self,
    ) -> DefinitionRegistry:
        """This should register the definitions for the agent.

        This is called when the agent is started, for each extensions. Extensions
        should register their definitions here and merge them with the agent's
        definition registry.


        Basic usage:

        ```python

        definition, actorBuilder = reactify(...)

        definition_registry.register_at_interface(
            "deploy_graph",
            definition=definition,
            structure_registry=self.structure_registry,
            actorBuilder=actorBuilder,
        )

        ```

        Merge Usage:

        ```python

        self.definition_registry = DefinitionRegistry()

        agent_definition_registry.merge_with(self.definition_registry)



        """
        ...

    async def atear_down(self):
        """This should be called when the agent is torn down"""
        ...
