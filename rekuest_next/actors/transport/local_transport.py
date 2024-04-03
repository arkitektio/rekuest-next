from abc import abstractmethod
from typing import Any, Awaitable, Callable, List, Optional, Union

from rekuest.messages import Assignation, Unassignation, Provision, Unprovision
from rekuest.api.schema import (
    LogLevelInput,
    ProvisionMode,
    ProvisionStatus,
    AssignationStatus,
)
from koil.composition import KoiledModel
from typing import Protocol, runtime_checkable
from rekuest.agents.transport.protocols.agent_json import (
    AssignationChangedMessage,
    ProvisionChangedMessage,
    ProvisionMode,
)
import logging
import asyncio
from rekuest.agents.transport.base import AgentTransport
from rekuest.actors.types import Passport, Assignment


logger = logging.getLogger(__name__)


@runtime_checkable
class Broadcast(Protocol):
    def __call__(
        self,
        assignation: Union[Assignation, Unassignation, Provision, Unprovision],
    ) -> Awaitable[None]:
        ...


class LocalTransport(KoiledModel):
    """Agent Transport

    A Transport is a means of communicating with an Agent. It is responsible for sending
    and receiving messages from the backend. It needs to implement the following methods:

    list_provision: Getting the list of active provisions from the backend. (depends on the backend)
    list_assignation: Getting the list of active assignations from the backend. (depends on the backend)

    change_assignation: Changing the status of an assignation. (depends on the backend)
    change_provision: Changing the status of an provision. (depends on the backend)

    broadcast: Configuring the callbacks for the transport on new assignation, unassignation provision and unprovison.

    if it is a stateful connection it can also implement the following methods:

    aconnect
    adisconnect

    """

    broadcast: Broadcast

    @property
    def connected(self):
        return True

    async def change_provision(
        self,
        id: str,
        status: ProvisionStatus = None,
        message: str = None,
        mode: ProvisionMode = None,
    ):
        await self.broadcast(
            ProvisionChangedMessage(
                provision=id, status=status, message=message, mode=mode
            )
        )

    async def change_assignation(
        self,
        id: str,
        status: AssignationStatus = None,
        message: str = None,
        returns: List[Any] = None,
        progress: int = None,
    ):
        await self.broadcast(
            AssignationChangedMessage(
                assignation=id, status=status, message=message, returns=returns
            )
        )

    async def log_to_provision(
        self,
        id: str,
        level: LogLevelInput = None,
        message: str = None,
    ):
        logger.info(f"{id} {level} {message}")

    async def log_to_assignation(
        self,
        id: str,
        level: LogLevelInput = None,
        message: str = None,
    ):
        logger.info(f"{id} {level} {message}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    class Config:
        underscore_attrs_are_private = True
        arbitrary_types_allowed = True
        copy_on_model_validation = False


class AgentActorAssignTransport(KoiledModel):
    actor_transport: "AgentActorTransport"
    assignment: Assignment

    async def change_assignation(
        self,
        status: AssignationStatus = None,
        message: str = None,
        returns: List[Any] = None,
        progress: int = None,
    ):
        await self.actor_transport.agent_transport.change_assignation(
            id=self.assignment.assignation,
            status=status,
            message=message,
            returns=returns,
            progress=progress,
        )

    async def log_to_assignation(
        self,
        level: LogLevelInput = None,
        message: str = None,
    ):
        await self.actor_transport.agent_transport.log_to_assignation(
            id=self.assignment.assignation, level=level or "DEBUG", message=message
        )

    class Config:
        underscore_attrs_are_private = True
        arbitrary_types_allowed = True
        copy_on_model_validation = False


class AgentActorTransport(KoiledModel):
    """Agent Transport

    A Transport is a means of communicating with an Agent. It is responsible for sending
    and receiving messages from the backend. It needs to implement the following methods:

    list_provision: Getting the list of active provisions from the backend. (depends on the backend)
    list_assignation: Getting the list of active assignations from the backend. (depends on the backend)

    change_assignation: Changing the status of an assignation. (depends on the backend)
    change_provision: Changing the status of an provision. (depends on the backend)

    broadcast: Configuring the callbacks for the transport on new assignation, unassignation provision and unprovison.

    if it is a stateful connection it can also implement the following methods:

    aconnect
    adisconnect

    """

    passport: Passport
    agent_transport: AgentTransport

    @property
    def connected(self):
        return True

    async def change_provision(
        self,
        status: ProvisionStatus = None,
        message: str = None,
        mode: ProvisionMode = None,
    ):
        await self.agent_transport.change_provision(
            self.passport.provision, status=status, message=message, mode=mode
        )

    async def log_to_provision(
        self,
        id: str,
        level: LogLevelInput = None,
        message: str = None,
    ):
        logger.info(f"{id} {level} {message}")
        await self.agent_transport.log_to_provision(
            id=self.passport.provision, level=level, message=message
        )

    def spawn(self, assignment: Assignment) -> AgentActorAssignTransport:
        return AgentActorAssignTransport(actor_transport=self, assignment=assignment)

    class Config:
        underscore_attrs_are_private = True
        arbitrary_types_allowed = True
        copy_on_model_validation = False


AgentActorAssignTransport.update_forward_refs()


class ProxyAssignTransport(KoiledModel):
    assignment: Assignment
    on_change: Callable
    on_log: Callable

    async def change(self, *args, **kwargs):
        await self.on_change(self.assignment, *args, **kwargs)  # Forwards assignment up

    async def log(self, *args, **kwargs):
        await self.on_log(self.assignment, *args, **kwargs)  # Forwards assignment up

    class Config:
        underscore_attrs_are_private = True
        arbitrary_types_allowed = True
        copy_on_model_validation = False


class ProxyActorTransport(KoiledModel):
    passport: Passport
    on_actor_log: Callable[[Passport, LogLevelInput, str], Awaitable[None]]
    on_actor_change: Callable[
        [Passport, ProvisionStatus, str, ProvisionMode], Awaitable[None]
    ]
    on_assign_change: Callable[
        [Assignment, AssignationStatus, str, List[Any], int], None
    ]
    on_assign_log: Callable[[Assignment, LogLevelInput, str], None]

    async def change(self, *args, **kwargs):
        await self.on_actor_change(self.passport, *args, **kwargs)

    async def log(self, *args, **kwargs):
        await self.on_actor_log(self.passport, *args, **kwargs)

    # Just forwaring the calls further up
    async def _change_assignation(self, *args, **kwargs):
        await self.on_assign_change(*args, **kwargs)

    async def _log_to_assignation(self, *args, **kwargs):
        await self.on_assign_log(*args, **kwargs)

    def spawn(self, assignment: Assignment) -> ProxyAssignTransport:
        return ProxyAssignTransport(
            assignment=assignment,
            on_change=self._change_assignation,
            on_log=self._log_to_assignation,
        )
