from abc import abstractmethod
from typing import Any, Awaitable, Callable, List, Optional, Union

from rekuest_next.messages import OutMessage, ProvisionEvent, AssignationEvent
from rekuest_next.api.schema import ProvisionEventKind, AssignationEventKind, LogLevel

from koil.composition import KoiledModel
from typing import Protocol, runtime_checkable
import logging
import asyncio
from rekuest_next.agents.transport.base import AgentTransport
from rekuest_next.actors.types import Passport, Assignment


logger = logging.getLogger(__name__)


class ProxyAssignTransport(KoiledModel):
    assignment: Assignment
    on_log: Callable[[OutMessage], Awaitable[None]]

    async def log_event(self, *args, **kwargs):
        await self.on_log(
            AssignationEvent(assignation=self.assignment.assignation, **kwargs)
        )  # Forwards assignment up

    class Config:
        arbitrary_types_allowed = True


class ProxyActorTransport(KoiledModel):
    passport: Passport
    on_log_event: Callable[[OutMessage], Awaitable[None]]

    async def log_event(self, **kwargs):
        await self.on_log_event(
            ProvisionEvent(provision=self.passport.provision, **kwargs)
        )

    def spawn(self, assignment: Assignment) -> ProxyAssignTransport:
        return ProxyAssignTransport(
            assignment=assignment,
            on_log=self.on_log_event,
        )
