from typing import Any, Optional, Literal, Union, Dict
from pydantic import BaseModel
from enum import Enum
from pydantic import Field
import uuid


class ToAgentMessageType(str, Enum):
    ASSIGN = "ASSIGN"
    CANCEL = "CANCEL"
    STEP = "STEP"
    COLLECT = "COLLECT"
    RESUME = "RESUME"
    PAUSE = "PAUSE"
    INTERRUPT = "INTERRUPT"
    PROVIDE = "PROVIDE"
    UNPROVIDE = "UNPROVIDE"
    INIT = "INIT"
    HEARTBEAT = "HEARTBEAT"
    
    
    
class FromAgentMessageType(str, Enum):
    REGISTER = "REGISTER"
    LOG = "LOG"
    PROGRESS = "PROGRESS"
    DONE = "DONE"
    YIELD = "YIELD"
    ERROR = "ERROR"
    PAUSED = "PAUSED"
    CRITICAL = "CRITICAL"
    STEPPED = "STEPPED"
    RESUMED = "RESUMED"
    CANCELLED = "CANCELLED"
    APP_CANCELLED = "APP_CANCELLED" # Cancelled by the app not the user how assigned
    ASSIGNED = "ASSIGNED"
    INTERRUPTED = "INTERRUPTED"
    HEARTBEAT_ANSWER = "HEARTBEAT_ANSWER"
    


class Message(BaseModel):
    # This is the local mapping of the message, reply messages should have the same id
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class Assign(Message):
    """ An assign call
    
    And assign call is the initial request to start a specific
    functionality and will have an assignation id, that will stand
    as a reference for all sub calls (Pause, Interrupt, Reumse, Collect...). 
    as well should be passed to all events within the assignation (
        Progress, Logs, Done, Error, etc)
    )
    """
    
    
    type: Literal[ToAgentMessageType.ASSIGN] = ToAgentMessageType.ASSIGN
    interface: str = Field(description="The registered interface")
    extension: str = Field(description="The extension that registered the interface")
    reservation: Optional[str] = Field(default=None, description="The reservation id if assigned through that")
    assignation: str = Field(description="The assignation id")
    root: Optional[str] = Field(default=None, description="The root of all cascaded assignations (user triggered assignation), None if this is the mother")
    """ The mother assignation (root)"""
    parent: Optional[str] = Field(default=None, description="The direct parent of this assignation, None if this is this is the mother")
    """ The parent s"""
    reference: Optional[str] = Field(default=None, description="A reference that the assinger provided")
    args: Optional[Dict[str, Any]] = Field(default=None, description="The arguments that was sendend")
    message: Optional[str] = None
    user: Optional[str] = Field(default=None, description="The assining user that was sendend")
    app: Optional[str] = Field(default=None, description="The assinging app")

    @property
    def actor_id(self):
        return f"{self.extension}.{self.interface}"

class Step(Message):
    type: Literal[ToAgentMessageType.STEP] = ToAgentMessageType.STEP
    assignation: int
    
    
class Heartbeat(Message):
    type: Literal[ToAgentMessageType.HEARTBEAT] = ToAgentMessageType.HEARTBEAT
    
class Pause(Message):
    """ A pause call
    
    A pause call tells the agent to pause the assignation
    and all its children assignation until a resume is received
    
    Its on the actor to decide what to do with the children assignations
    (i.e. pause them, cancel them, etc) or to raise an error if the
    state of the assignaiton wouldn't allow this.
    
    """
    type: Literal[ToAgentMessageType.PAUSE] = ToAgentMessageType.PAUSE
    assignation: int

class Resume(Message):
    """ A resume call
    
    A resume call unpauses the pause"""
    type: Literal[ToAgentMessageType.RESUME] = ToAgentMessageType.RESUME
    assignation: int


class Cancel(Message):
    """ A cancel call
    
    A cancellation call is a request from the user to
    cancel an assignation nicely (i.e by also nicely
    cancelling all the children assignations). 
    Cancel represent a "nice alternative" to the interrupt call.
    While a cancellation of a mother task is only send to
    the mother to kill the children nicely (what the fuck is
    this metaphor), a interrupt will be send to all children
    automatically without the mother.
    

    Find more information on this in the arkitekt.live
    """
    
    type: Literal[ToAgentMessageType.CANCEL] = ToAgentMessageType.CANCEL
    assignation: int

class Collect(Message):
    """ A collect call
    
    A collect call tells the agent to collect data LOCALLY,
    by deleting data on the "shelves" that live in memory.
    
    Find more information on this in the arkitekt.live
    documentation on local workflwos
    
    
    """
    type: Literal[ToAgentMessageType.COLLECT] = ToAgentMessageType.COLLECT
    assignation: int


class Interrupt(Message):
    type: Literal[ToAgentMessageType.INTERRUPT] = ToAgentMessageType.INTERRUPT
    assignation: int



class CancelledEvent(Message):
    type: Literal[FromAgentMessageType.CANCELLED] = FromAgentMessageType.CANCELLED
    assignation: str
    
class InterruptedEvent(Message):
    type: Literal[FromAgentMessageType.INTERRUPTED] = FromAgentMessageType.INTERRUPTED
    assignation: str
    
class PausedEvent(Message):
    type: Literal[FromAgentMessageType.PAUSED] = FromAgentMessageType.PAUSED
    assignation: str
    
    
class ResumedEvent(Message):
    type: Literal[FromAgentMessageType.RESUMED] = FromAgentMessageType.RESUMED
    assignation: str
    
class SteppedEvent(Message):
    type: Literal[FromAgentMessageType.STEPPED] = FromAgentMessageType.STEPPED
    

class LogEvent(Message):
    type: Literal[FromAgentMessageType.LOG] = FromAgentMessageType.LOG
    assignation: str
    message: str
    
class ProgressEvent(Message):
    type: Literal[FromAgentMessageType.PROGRESS] = FromAgentMessageType.PROGRESS
    assignation: str
    progress: Optional[int] = None
    message: Optional[str] = None
    
class YieldEvent(Message):
    type: Literal[FromAgentMessageType.YIELD] = FromAgentMessageType.YIELD
    assignation: str
    returns: Optional[Dict[str, Any]] = None
    
class DoneEvent(Message):
    type: Literal[FromAgentMessageType.DONE] = FromAgentMessageType.DONE
    assignation: str
    
class ErrorEvent(Message):
    type: Literal[FromAgentMessageType.ERROR] = FromAgentMessageType.ERROR
    assignation: str
    error: str
    
class CriticalEvent(Message):
    type: Literal[FromAgentMessageType.CRITICAL] = FromAgentMessageType.CRITICAL
    assignation: str
    error: str
    
    
class HeartbeatEvent(Message):
    type: Literal[FromAgentMessageType.HEARTBEAT_ANSWER] = FromAgentMessageType.HEARTBEAT_ANSWER


class AssignInquiry(BaseModel):
    assignation: str


class Register(Message):
    type: Literal[FromAgentMessageType.REGISTER] = FromAgentMessageType.REGISTER
    instance_id: str 
    token: str


class Init(Message):
    type: Literal[ToAgentMessageType.INIT] = ToAgentMessageType.INIT
    instance_id: str = None
    agent: str = None
    registry: str = None
    inquiries: list[AssignInquiry] = []


ToAgentMessage = Union[Init, Assign, Cancel, Interrupt, Heartbeat, Step, Pause, Resume, Collect]
FromAgentMessage = Union[CriticalEvent, LogEvent, ProgressEvent, DoneEvent, ErrorEvent, YieldEvent, Register, HeartbeatEvent, SteppedEvent, ResumedEvent, PausedEvent, CancelledEvent, InterruptedEvent]
