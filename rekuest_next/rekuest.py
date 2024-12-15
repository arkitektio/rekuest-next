from typing import Dict
from pydantic import Field
from koil.helpers import unkoil_task
from rekuest_next.api.schema import Template
from rekuest_next.postmans.graphql import GraphQLPostman
from rekuest_next.rath import RekuestNextRath
from rekuest_next.structures.default import get_default_structure_registry
from rekuest_next.structures.registry import (
    StructureRegistry,
)

from rekuest_next.agents.base import BaseAgent
from rekuest_next.postmans.base import BasePostman
from koil import unkoil
from koil.composition import Composition
from koil.decorators import koilable
from rekuest_next.register import register


@koilable(fieldname="koil", add_connectors=True)
class RekuestNext(Composition):
    rath: RekuestNextRath = Field(default_factory=RekuestNextRath)
    structure_registry: StructureRegistry = Field(
        default_factory=get_default_structure_registry
    )
    agent: BaseAgent = Field(default_factory=BaseAgent)
    postman: BasePostman = Field(default_factory=GraphQLPostman)

    registered_templates: Dict[str, Template] = Field(default_factory=dict)

    def register(self, *args, **kwargs) -> None:
        """
        Register a new function
        """

        return register(
            *args,
            **kwargs,
        )

    def run(self, *args, **kwargs) -> None:
        """
        Run the application.
        """
        return unkoil(self.arun, *args, **kwargs)

    def run_detached(self, *args, **kwargs) -> None:
        """
        Run the application detached.
        """
        return unkoil_task(self.arun, *args, **kwargs)

    async def arun(self) -> None:
        """
        Run the application.
        """
        await self.agent.aprovide()

    def _repr_html_inline_(self):
        return f"<table><tr><td>rath</td><td>{self.rath._repr_html_inline_()}</td></tr></table>"
