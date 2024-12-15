from typing import Any, Awaitable, Callable, List, Union

from pydantic import ConfigDict

from rekuest_next.messages import Assignation, Unassignation, Provision, Unprovision
from rekuest_next.api.schema import (
    LogLevelInput,
    ProvisionMode,
    ProvisionStatus,
    AssignationStatus,
)
from koil.composition import KoiledModel
from typing import Protocol, runtime_checkable
from rekuest_next.agents.transport.protocols.agent_json import (
    AssignationChangedMessage,
    ProvisionChangedMessage,
    ProvisionMode,
)
import logging
from rekuest_nextagents.transport.base import AgentTransport
from rekuest_nextactors.types import Passport, Assignment


logger = logging.getLogger(__name__)


@runtime_checkable
class Broadcast(Protocol):
    def __call__(
        self,
        assignation: Union[Assignation, Unassignation, Provision, Unprovision],
    ) -> Awaitable[None]: ...


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
    model_config = ConfigDict(arbitrary_types_allowed=True)

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



class AgentActorAssignTransport(KoiledModel):
    actor_transport: "AgentActorTransport"
    assignment: Assignment
    model_config = ConfigDict(arbitrary_types_allowed=True)

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


AgentActorAssignTransport.model_rebuild()


class ProxyAssignTransport(KoiledModel):
    assignment: Assignment
    on_change: Callable
    on_log: Callable

    async def change_assignation(self, *args, **kwargs):
        await self.on_change(self.assignment, *args, **kwargs)

    async def log_to_assignation(self, *args, **kwargs):
        await self.on_log(self.assignment, *args, **kwargs)


class ProxyActorTransport(KoiledModel):
    on_log: Callable
    on_change: Callable
    on_assign_change: Callable
    on_assign_log: Callable

    async def change_provision(self, *args, **kwargs):
        await self.on_change(*args, **kwargs)

    async def log_to_provision(self, *args, **kwargs):
        await self.on_log(*args, **kwargs)

    async def change_assignation(self, *args, **kwargs):
        await self.on_assign_change(*args, **kwargs)

    async def log_to_assignation(self, *args, **kwargs):
        await self.on_assign_log(*args, **kwargs)

    def spawn(self, assignment: Assignment) -> AgentActorAssignTransport:
        return ProxyAssignTransport(
            assignment=assignment,
            on_change=self.change_assignation,
            on_log=self.log_to_assignation,
        )
