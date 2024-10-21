from rekuest_next.actors.types import Passport
from rekuest_next.messages import Assign
from rekuest_next.structures.default import (
    get_default_structure_registry,
    StructureRegistry,
)
from pydantic import BaseModel, Field
from typing import Dict, Any, List
import logging


logger = logging.getLogger(__name__)


class AssignationCollector(BaseModel):
    assignment: Assign

    async def collect(self):
        """
        Collect data from the source.

        :return: The collected data.
        """
        raise NotImplementedError

    async def register(self, args: List[Any]):
        return


class ActorCollector(BaseModel):
    """
    The ActorCollector class is used to collect data in the course of a
    an anctors life time. It initiates Assignation that then in turn
    collect data during the Assignation liftetime
    """

    passport: Passport
    sub_collectors: Dict[str, AssignationCollector] = Field(default_factory=dict)
    delegated_collector: Dict[str, "ActorCollector"] = Field(default_factory=dict)

    def spawn(self, assignment: Assign):
        """
        Spawn a new collector for the given assignation.
        """
        assign_collector = AssignationCollector(assignment=assignment)
        self.sub_collectors[assignment.parent] = assign_collector
        return assign_collector

    async def collect(self, assignment: Assign):
        """
        Collect data from the source.

        :return: The collected data.
        """
        raise NotImplementedError


class Collector(BaseModel):
    """
    The Collector class is used to collect data in the course of a
    an agents life time. It initiates ActorCollectors that then in turn
    collect data during the actors liftetime
    """

    structure_registry: StructureRegistry = Field(
        default_factory=get_default_structure_registry
    )

    assignment_map: Dict[str, List[Any]] = Field(default_factory=dict)
    children_tree: Dict[str, List[str]] = Field(default_factory=dict)

    def register(self, assignment: Assign, items: List[any]):
        logger.debug(f"Registering {assignment.id}")

        if assignment.id in self.assignment_map:
            self.assignment_map[assignment.id] += items
        else:
            self.assignment_map[assignment.id] = items
        if assignment.parent:
            if assignment.parent in self.children_tree:
                self.children_tree[assignment.parent].append(assignment.id)
            else:
                self.children_tree[assignment.parent] = [assignment.id]

    async def collect(self, id: str):
        """
        Collect data from the source.

        :return: The collected data.
        """

        if id in self.assignment_map:
            for identifier, value in self.assignment_map[id]:
                try:
                    collector = self.structure_registry.get_collector_for_identifier(
                        identifier
                    )
                    await collector(value)
                except Exception as e:
                    logger.critical(
                        f"Error while collecting {identifier} with value {value}"
                    )
                    raise e

        if id in self.children_tree:
            for child in self.children_tree[id]:
                await self.collect(child)
