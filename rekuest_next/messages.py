from typing import Any, Optional, Literal, Union, Dict
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
    # This is the local mapping of the message, reply messages should have the same id
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: MessageType


class Assign(Message):
    type: Literal[MessageType.ASSIGN] = MessageType.ASSIGN
    mother: Optional[int] = None
    """ The mother assignation (root)"""
    parent: Optional[int] = None
    """ The parent assignation"""
    assignation: int
    reference: Optional[str] = None
    provision: Optional[int] = None
    reservation: Optional[int] = None
    args: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    user: Optional[str] = None


class Cancel(Message):
    type: Literal[MessageType.CANCEL] = MessageType.CANCEL
    assignation: int


class Interrupt(Message):
    type: Literal[MessageType.INTERRUPT] = MessageType.INTERRUPT
    assignation: int


class Provide(Message):
    type: Literal[MessageType.PROVIDE] = MessageType.PROVIDE
    provision: int


class Unprovide(Message):
    type: Literal[MessageType.UNPROVIDE] = MessageType.UNPROVIDE
    provision: int
    message: Optional[str] = None


class AssignationEvent(Message):
    type: Literal[MessageType.ASSIGNATION_EVENT] = MessageType.ASSIGNATION_EVENT
    assignation: int
    kind: AssignationEventKind
    message: Optional[str] = None
    returns: Optional[Dict[str, Any]] = None
    persist: Optional[bool] = None
    progress: Optional[int] = None
    log: Optional[bool] = None
    status: Optional[AssignationEventKind] = None


class ProvisionEvent(Message):
    type: Literal[MessageType.PROVISION_EVENT] = MessageType.PROVISION_EVENT
    provision: int
    kind: ProvisionEventKind
    message: Optional[str] = None
    user: Optional[str] = None


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
