from typing import Any, List, Optional, TypeVar, Literal, Union, Dict
from pydantic import BaseModel
from rekuest_next.api.schema import (
    AssignationEventKind,
    ProvisionEventKind,
)
from enum import Enum
from pydantic import Field
import uuid


class MessageType(str, Enum):
    ASSIGN = "ASSIGN"
    CANCEL = "CANCEL"
    INTERRUPT = "INTERRUPT"
    PROVIDE = "PROVIDE"
    UNPROVIDE = "UNPROVIDE"
    ASSIGNATION_EVENT = "ASSIGNATION_EVENT"
    PROVISION_EVENT = "PROVISION_EVENT"
    INIT = "INIT"
    HEARTBEAT = "HEARTBEAT"


class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: MessageType


class Assign(Message):
    type: Literal[MessageType.ASSIGN] = MessageType.ASSIGN
    assignation: str
    reference: Optional[str]
    provision: Optional[str]
    reservation: Optional[str]
    args: Optional[Dict[str, Any]]
    message: Optional[str]
    user: Optional[str]


class Cancel(Message):
    type: Literal[MessageType.CANCEL] = MessageType.CANCEL
    assignation: str
    provision: str


class Interrupt(Message):
    type: Literal[MessageType.INTERRUPT] = MessageType.INTERRUPT
    assignation: str
    provision: str


class Provide(Message):
    type: Literal[MessageType.PROVIDE] = MessageType.PROVIDE
    provision: str


class Unprovide(Message):
    type: Literal[MessageType.UNPROVIDE] = MessageType.UNPROVIDE
    provision: str
    message: Optional[str]


class AssignationEvent(Message):
    type: Literal[MessageType.ASSIGNATION_EVENT] = MessageType.ASSIGNATION_EVENT
    assignation: str
    kind: AssignationEventKind
    message: Optional[str]
    returns: Optional[Dict[str, Any]] = Field(default_factory=None)
    persist: Optional[bool]
    progress: Optional[int]
    log: Optional[bool]
    status: Optional[AssignationEventKind]


class ProvisionEvent(Message):
    type: Literal[MessageType.PROVISION_EVENT] = MessageType.PROVISION_EVENT
    provision: str
    kind: ProvisionEventKind
    message: Optional[str]
    user: Optional[str]


class AssignInquiry(BaseModel):
    assignation: str


class ProvideInquiry(BaseModel):
    provision: str


class Init(Message):
    type: Literal[MessageType.INIT] = MessageType.INIT
    instance_id: str = None
    agent: str = None
    registry: str = None
    provisions: list[Provide] = []
    inquiries: list[AssignInquiry] = []


InMessage = Union[Init, Assign, Cancel, Interrupt, Provide, Unprovide]
OutMessage = Union[AssignationEvent, ProvisionEvent]
