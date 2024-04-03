import asyncio
import logging
from typing import Any, Dict, List, Optional, Protocol, Union, runtime_checkable

from pydantic import BaseModel, Field, PrivateAttr

from koil.types import Contextual
from rekuest.actors.errors import UnknownMessageError
from rekuest.agents.transport.base import AgentTransport
from rekuest.api.schema import (
    AssignationLogLevel,
    AssignationStatus,
    LogLevelInput,
    ProvisionLogLevel,
    ProvisionMode,
    ProvisionStatus,
)
from rekuest.definition.define import DefinitionInput
from rekuest.messages import Assignation, Provision, Unassignation
from rekuest.structures.registry import (
    StructureRegistry,
)
from rekuest.actors.types import Passport, Assignment


@runtime_checkable
class ActorTransport(Protocol):
    passport: Passport

    async def change(
        self,
        status: ProvisionStatus = None,
        message: str = None,
        mode: ProvisionMode = None,
    ):
        ...

    async def log(
        self,
        level: LogLevelInput = None,
        message: str = None,
    ):
        ...

    def spawn(self, assignment: Assignment) -> "AssignTransport":
        ...


@runtime_checkable
class AssignTransport(Protocol):
    assignment: Assignment

    async def change(
        self,
        status: AssignationStatus = None,
        message: str = None,
        returns: List[Any] = None,
        progress: int = None,
    ):
        ...

    async def log(
        self,
        level: LogLevelInput = None,
        message: str = None,
    ):
        ...
