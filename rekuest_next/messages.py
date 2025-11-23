"""Messages that are used to communicate between the rekuest backend and the agent"""

from typing import Any, Optional, Literal, Union, Dict
from pydantic import BaseModel, ConfigDict
from enum import Enum
from pydantic import Field
import uuid


JSONSerializable = Union[
    str, int, float, bool, None, dict[str, "JSONSerializable"], list["JSONSerializable"]
]


ShallowJSONSerializable = Union[str, int, float, bool, None, dict[str, Any], list[Any]]  # type: ignore

LogLevelLiteral = Literal[
    "DEBUG",
    "INFO",
    "ERROR",
    "WARN",
    "CRITICAL",
]


class LogLevel(str, Enum):
    """No documentation"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    ERROR = "ERROR"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class ToAgentMessageType(str, Enum):
    """The message types that can be sent to the agent from the rekuest backend"""

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
    BOUNCE = "BOUNCE"
    KICK = "KICK"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"


class FromAgentMessageType(str, Enum):
    """The message types that can be sent from the agent to the rekuest backend"""

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
    APP_CANCELLED = "APP_CANCELLED"  # Cancelled by the app not the user how assigned
    ASSIGNED = "ASSIGNED"
    INTERRUPTED = "INTERRUPTED"
    HEARTBEAT_ANSWER = "HEARTBEAT_ANSWER"


class Message(BaseModel):
    """A base message class"""

    # This is the local mapping of the message, reply messages should have the same id
    model_config = ConfigDict(use_enum_values=True, frozen=True)
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class Assign(Message):
    """An assign call

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
    reservation: Optional[str] = Field(
        default=None, description="The reservation id if assigned through that"
    )
    assignation: str = Field(description="The assignation id")
    root: Optional[str] = Field(
        default=None,
        description="The root of all cascaded assignations (user triggered assignation), None if this is the mother",
    )
    """ The mother assignation (root)"""
    parent: Optional[str] = Field(
        default=None,
        description="The direct parent of this assignation, None if this is this is the mother",
    )
    """ The parent s"""
    dependencies: Dict[str, str] | None = Field(
        default=None,
        description="The dependencies that were provided (should map reference to template)",
    )
    capture: bool = Field(default=False, description="Whether to run in debug mode")
    reference: Optional[str] = Field(
        default=None, description="A reference that the assinger provided"
    )
    args: Dict[str, ShallowJSONSerializable] = Field(
        description="The arguments that was sendend"
    )
    message: Optional[str] = None
    user: str = Field(..., description="The assinging user")
    org: Optional[str] = Field(
        default=None, description="The org that the user currently belongs to"
    )
    app: str = Field(description="The assinging app")
    action: str = Field(description="The action that triggered this assignation")

    @property
    def actor_id(self) -> str:
        """The actor id is the id of the actor that will be used to run this assignation"""
        return f"{self.extension}.{self.interface}"


class Step(Message):
    """A step call
    A step call tells the agent to step the assignation
    and all its children assignation until a resume is received
    Its on the actor to decide what to do with the children assignations
    """

    type: Literal[ToAgentMessageType.STEP] = ToAgentMessageType.STEP
    assignation: str


class Bounce(Message):
    """A step call
    A step call tells the agent to step the assignation
    and all its children assignation until a resume is received
    Its on the actor to decide what to do with the children assignations
    """

    type: Literal[ToAgentMessageType.BOUNCE] = ToAgentMessageType.BOUNCE
    duration: int | None = None


class Kick(Message):
    """A step call
    A step call tells the agent to step the assignation
    and all its children assignation until a resume is received
    Its on the actor to decide what to do with the children assignations
    """

    type: Literal[ToAgentMessageType.KICK] = ToAgentMessageType.KICK
    reason: str | None = None


class Heartbeat(Message):
    """A heartbeat call
    A heartbeat call tells the agent to send a heartbeat
    and all its children assignation until a resume is received
    Its on the actor to decide what to do with the children assignations
    """

    type: Literal[ToAgentMessageType.HEARTBEAT] = ToAgentMessageType.HEARTBEAT


class Pause(Message):
    """A pause call

    A pause call tells the agent to pause the assignation
    and all its children assignation until a resume is received

    Its on the actor to decide what to do with the children assignations
    (i.e. pause them, cancel them, etc) or to raise an error if the
    state of the assignaiton wouldn't allow this.

    """

    type: Literal[ToAgentMessageType.PAUSE] = ToAgentMessageType.PAUSE
    assignation: str


class Resume(Message):
    """A resume call

    A resume call unpauses the pause"""

    type: Literal[ToAgentMessageType.RESUME] = ToAgentMessageType.RESUME
    assignation: str


class Cancel(Message):
    """A cancel call

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
    assignation: str


class Collect(Message):
    """A collect call

    A collect call tells the agent to collect data LOCALLY,
    by deleting data on the "shelves" that live in memory.

    Find more information on this in the arkitekt.live
    documentation on local workflwos


    """

    type: Literal[ToAgentMessageType.COLLECT] = ToAgentMessageType.COLLECT
    drawers: list[str]


class Interrupt(Message):
    """A interrupt"""

    type: Literal[ToAgentMessageType.INTERRUPT] = ToAgentMessageType.INTERRUPT
    assignation: str


class CancelledEvent(Message):
    """A cancelled event"""

    type: Literal[FromAgentMessageType.CANCELLED] = FromAgentMessageType.CANCELLED
    assignation: str


class InterruptedEvent(Message):
    """An interrupted event

    A interruppted event is sent when the assignation was
    successfully interrupted by the actor.


    """

    type: Literal[FromAgentMessageType.INTERRUPTED] = FromAgentMessageType.INTERRUPTED
    assignation: str


class PausedEvent(Message):
    """A paused event

    A paused event is sent when the assignation was
    successfully paused by the actor.


    """

    type: Literal[FromAgentMessageType.PAUSED] = FromAgentMessageType.PAUSED
    assignation: str


class ResumedEvent(Message):
    """A resumed event

    A resumed event is sent when the assignation was
    successfully resumed by the actor.


    """

    type: Literal[FromAgentMessageType.RESUMED] = FromAgentMessageType.RESUMED
    assignation: str


class SteppedEvent(Message):
    """A stepped event

    A stepped event is sent when the assignation was
    successfully stepped by the actor and it has now
    stopped at another breakpoint.


    """

    type: Literal[FromAgentMessageType.STEPPED] = FromAgentMessageType.STEPPED


class LogEvent(Message):
    """A log event

    A log event is sent when the agent wants to send a log
    message to the rekuest backend. This is used to
    send logs from the agent to the rekuest backend
    """

    type: Literal[FromAgentMessageType.LOG] = FromAgentMessageType.LOG
    assignation: str
    message: str
    level: LogLevelLiteral = "INFO"
    """The log level of the message"""


class ProgressEvent(Message):
    """A progress event

    A progress event is sent when the agent wants to send a
    progress message to the rekuest backend. This is used to
    send progress from the agent to the rekuest backend
    """

    type: Literal[FromAgentMessageType.PROGRESS] = FromAgentMessageType.PROGRESS
    assignation: str
    progress: Optional[int] = None
    message: Optional[str] = None


class YieldEvent(Message):
    """A yield event

    A yield event is sent when the agent wants to send a
    yielded assignmented message to the rekuest backend. This is used to
    send yield from the agent to the rekuest backend
    """

    type: Literal[FromAgentMessageType.YIELD] = FromAgentMessageType.YIELD
    assignation: str
    returns: Optional[Dict[str, Any]] = None


class DoneEvent(Message):
    """A done event

    A done event is sent when the actor has finished the assignation
    and all its children assignation. This is used to
    send done from the agent to the rekuest backend
    """

    type: Literal[FromAgentMessageType.DONE] = FromAgentMessageType.DONE
    assignation: str


class ErrorEvent(Message):
    """An error event

    An error event is sent when the agent wants to send an error
    message to the rekuest backend. This is used to
    send errors from the agent to the rekuest backend.

    Errors are potentially recoverable, while critical errors are not.
    """

    type: Literal[FromAgentMessageType.ERROR] = FromAgentMessageType.ERROR
    assignation: str
    error: str


class CriticalEvent(Message):
    """A critical event

    A critical event is sent when the agent wants to send a critical
    message to the rekuest backend. This is used to
    send critical errors from the agent to the rekuest backend
    """

    type: Literal[FromAgentMessageType.CRITICAL] = FromAgentMessageType.CRITICAL
    assignation: str
    error: str


class HeartbeatEvent(Message):
    """A heartbeat event

    A heartbeat event is sent when the agent replies to a heartbeat
    message from the rekuest backend. Agents should never send
    heartbeat events, but only reply to them.
    """

    type: Literal[FromAgentMessageType.HEARTBEAT_ANSWER] = (
        FromAgentMessageType.HEARTBEAT_ANSWER
    )


class AssignInquiry(BaseModel):
    """An assign inquiry

    An assign inquiry is a request from rekuest_backend to the agent
    to check the state of a specific assignation. This is used to check if the
    assignation is still running or if after a reconnect has died.
    """

    assignation: str


class Register(Message):
    """A register message

    A register message is sent from the agent to the rekuest backend
    to register the agent with the rekuest backend. This is used to
    register the agent with the rekuest backend and to send the
    agent's token to the rekuest backend.

    """

    type: Literal[FromAgentMessageType.REGISTER] = FromAgentMessageType.REGISTER
    instance_id: str
    token: str


class ProtocolError(Message):
    type: Literal[ToAgentMessageType.PROTOCOL_ERROR] = ToAgentMessageType.PROTOCOL_ERROR
    error: str
    """ The error message that was raised by the agent"""


class Init(Message):
    """An init message

    An init message is sent from the rekuest backend to the agent
    as a response to the register message. It contains the
    information about the agent and the rekuest backend.
    """

    type: Literal[ToAgentMessageType.INIT] = ToAgentMessageType.INIT
    instance_id: str
    agent: str
    inquiries: list[AssignInquiry] = []


ToAgentMessage = Union[
    Init,
    Assign,
    Cancel,
    Interrupt,
    Heartbeat,
    Step,
    Pause,
    Resume,
    Collect,
    ProtocolError,
    Bounce,
    Kick,
]
FromAgentMessage = Union[
    CriticalEvent,
    LogEvent,
    ProgressEvent,
    DoneEvent,
    ErrorEvent,
    YieldEvent,
    Register,
    HeartbeatEvent,
    SteppedEvent,
    ResumedEvent,
    PausedEvent,
    CancelledEvent,
    InterruptedEvent,
]
