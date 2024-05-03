import asyncio
import logging
from typing import Any, Dict, List, Optional, Protocol, Union, runtime_checkable

from pydantic import BaseModel, Field, PrivateAttr

from koil.types import Contextual
from rekuest_next.actors.types import Assignment, Passport
from rekuest_next.api.schema import ProvisionEventKind, AssignationEventKind, LogLevel


@runtime_checkable
class ActorTransport(Protocol):
    passport: Passport

    async def log_event(
        self,
        kind: ProvisionEventKind = None,
        message: str = None,
        level: LogLevel = None,
    ): ...

    def spawn(self, assignment: Assignment) -> "AssignTransport": ...


@runtime_checkable
class AssignTransport(Protocol):
    assignment: Assignment

    async def log_event(
        self,
        kind: AssignationEventKind = None,
        message: str = None,
        returns: List[Any] = None,
        progress: int = None,
    ): ...
