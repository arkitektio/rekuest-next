"""The base client for rekuest next"""

from pydantic import Field
from koil.helpers import unkoil_task
from rekuest_next.postmans.graphql import GraphQLPostman
from rekuest_next.agents.base import BaseAgent
from rekuest_next.rath import RekuestNextRath

from rekuest_next.actors.types import Agent
from rekuest_next.postmans.types import Postman
from koil import unkoil
from koil.composition import Composition
from koil.decorators import koilable
from rekuest_next.register import register


@koilable(fieldname="koil", add_connectors=True)
class RekuestNext(Composition):
    """The main rekuest next client class"""

    rath: RekuestNextRath = Field(default_factory=RekuestNextRath)
    agent: Agent = Field(default_factory=BaseAgent)
    postman: Postman = Field(default_factory=GraphQLPostman)

    def register(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        """
        Register a new function
        """

        return register(*args, **kwargs)

    def run(self, instance_id: str | None = None) -> None:
        """
        Run the application.
        """
        return unkoil(self.arun, instance_id=instance_id)

    def run_detached(self, instance_id: str | None = None) -> None:
        """
        Run the application detached.
        """
        return unkoil_task(self.arun, instance_id=instance_id)

    async def arun(self, instance_id: str | None = None) -> None:
        """
        Run the application.
        """
        await self.agent.aprovide(instance_id=instance_id)
