# JSON RPC Messages
import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional, Any

from typing_extensions import Literal
from rekuest_next.api.schema import AssignationEventKind, ProvisionStatus
from rekuest_next.messages import (
    Assignation,
    AssignationLog,
    Provision,
    ProvisionLog,
    Unassignation,
    Unprovision,
    Inquiry,
)
from pydantic import BaseModel, Field


class AgentMessageTypes(str, Enum):
    ASSIGN_CHANGED = "ASSIGN_CHANGED"
    PROVIDE_CHANGED = "PROVIDE_CHANGED"

    ASSIGN_LOG = "ASSIGN_LOG"
    PROVIDE_LOG = "PROVIDE_LOG"

    LIST_ASSIGNATIONS = "LIST_ASSIGNATIONS"
    LIST_ASSIGNATIONS_REPLY = "LIST_ASSIGNATIONS_REPLY"
    LIST_ASSIGNATIONS_DENIED = "LIST_ASSIGNATIONS_DENIED"

    LIST_PROVISIONS = "LIST_PROVISIONS"
    LIST_PROVISIONS_REPLY = "LIST_PROVISIONS_REPLY"
    LIST_PROVISIONS_DENIED = "LIST_PROVISIONS_DENIED"


class AgentSubMessageTypes(str, Enum):
    HELLO = "HELLO"
    ASSIGN = "ASSIGN"
    PROVIDE = "PROVIDE"
    INQUIRY = "INQUIRY"
    UNPROVIDE = "UNPROVIDE"
    CANCEL = "CANCEL"
    INTERRUPT = "INTERRUPT"


class JSONMeta(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class JSONMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    meta: JSONMeta = Field(default_factory=JSONMeta)


class AssignationsList(JSONMessage):
    type: Literal[AgentMessageTypes.LIST_ASSIGNATIONS] = (
        AgentMessageTypes.LIST_ASSIGNATIONS
    )
    exclude: Optional[List[AssignationEventKind]]


class AssignationsListReply(JSONMessage):
    type: Literal[AgentMessageTypes.LIST_ASSIGNATIONS_REPLY] = (
        AgentMessageTypes.LIST_ASSIGNATIONS_REPLY
    )
    assignations: List[Assignation]


class AssignationsListDenied(JSONMessage):
    type: Literal[AgentMessageTypes.LIST_ASSIGNATIONS_DENIED] = (
        AgentMessageTypes.LIST_ASSIGNATIONS_DENIED
    )
    error: str


class ProvisionList(JSONMessage):
    type: Literal[AgentMessageTypes.LIST_PROVISIONS] = AgentMessageTypes.LIST_PROVISIONS
    exclude: Optional[List[AssignationEventKind]]


class ProvisionListReply(JSONMessage):
    type: Literal[AgentMessageTypes.LIST_PROVISIONS_REPLY] = (
        AgentMessageTypes.LIST_PROVISIONS_REPLY
    )
    provisions: List[Provision]


class ProvisionListDenied(JSONMessage):
    type: Literal[AgentMessageTypes.LIST_PROVISIONS_DENIED] = (
        AgentMessageTypes.LIST_PROVISIONS_DENIED
    )
    error: str


class ProvisionChangedMessage(JSONMessage):
    type: Literal[AgentMessageTypes.PROVIDE_CHANGED] = AgentMessageTypes.PROVIDE_CHANGED
    status: Optional[ProvisionStatus]
    message: Optional[str]
    provision: str


class InquirySubMessage(JSONMessage, Inquiry):
    type: Literal[AgentSubMessageTypes.INQUIRY] = AgentSubMessageTypes.INQUIRY


class ProvideSubMessage(JSONMessage, Provision):
    type: Literal[AgentSubMessageTypes.PROVIDE] = AgentSubMessageTypes.PROVIDE


class HelloSubMessage(JSONMessage):
    type: Literal[AgentSubMessageTypes.HELLO] = AgentSubMessageTypes.HELLO
    agent: str
    registry: str
    provisions: List[Provision]


class CancelMessage(JSONMessage):
    type: Literal[AgentSubMessageTypes.CANCEL] = AgentSubMessageTypes.CANCEL
    assignation: str


class InterruptMessage(JSONMessage):
    type: Literal[AgentSubMessageTypes.INTERRUPT] = AgentSubMessageTypes.INTERRUPT
    assignation: str


class AssignMessage(JSONMessage):
    type: Literal[AgentSubMessageTypes.ASSIGN] = AgentSubMessageTypes.ASSIGN
    assignation: str
    reference: Optional[str]
    provision: Optional[str]
    reservation: Optional[str]
    args: Optional[List[Any]]
    returns: Optional[List[Any]]
    persist: Optional[bool]
    progress: Optional[int]
    log: Optional[bool]
    status: Optional[AssignationEventKind]
    message: Optional[str]
    user: Optional[str]


class ProvisionMessage(JSONMessage):
    type: Literal[AgentSubMessageTypes.PROVIDE] = AgentSubMessageTypes.PROVIDE


class UnprovideSubMessage(JSONMessage, Unprovision):
    type: Literal[AgentSubMessageTypes.UNPROVIDE] = AgentSubMessageTypes.UNPROVIDE


class AssignationChangedMessage(JSONMessage, Assignation):
    type: Literal[AgentMessageTypes.ASSIGN_CHANGED] = AgentMessageTypes.ASSIGN_CHANGED


class AssignationLogMessage(JSONMessage, AssignationLog):
    type: Literal[AgentMessageTypes.ASSIGN_LOG] = AgentMessageTypes.ASSIGN_LOG


class ProvisionLogMessage(JSONMessage, ProvisionLog):
    type: Literal[AgentMessageTypes.PROVIDE_LOG] = AgentMessageTypes.PROVIDE_LOG
