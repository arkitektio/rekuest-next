"""Messages that are used to communicate between the rekuest backend and the agent.

Naming convention — the role lives in the affix and the direction is unambiguous:

- **Backend → Agent commands**: bare imperative (``Assign``, ``Cancel``, ``Pause``).
- **Agent → Backend reports**: bare past/noun (``Completed``, ``Failed``, ``Progress``).
- **Caller → Backend requests**: ``…Request`` suffix (``AssignRequest``, ``CancelRequest``).
- **Backend → Caller acks**: ``…Response`` suffix (``AssignResponse``, ``ControlResponse``).
- **Backend → Caller event stream**: ``…Event`` suffix (``CompletedEvent``, ``ProgressEvent``).

No names collide because commands are imperative, agent reports are bare past-tense, and
the caller stream carries the ``…Event`` suffix (``Pause`` cmd vs ``Paused`` report vs
``PausedEvent`` stream).
"""

from typing import Any, List, Optional, Literal, Union, Dict
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


class AgentMode(str, Enum):
    """How a participant intends to use the single agent protocol.

    The mode is requested on ``Register`` but only *granted* if the token carries the
    matching capability scopes (see ``facade.capabilities``). It maps onto the two
    independent capability axes ``executes_work`` and ``can_assign_root``:

    - ``EXECUTOR``     — runs tasks (executes_work), may not originate roots.
    - ``CALLER``       — originates root tasks (can_assign_root), does not execute.
    - ``ORCHESTRATOR`` — both executes work and originates roots.
    - ``OBSERVER``     — neither; a read-only dashboard that only streams events.
    """

    EXECUTOR = "EXECUTOR"
    CALLER = "CALLER"
    ORCHESTRATOR = "ORCHESTRATOR"
    OBSERVER = "OBSERVER"


class ToAgentMessageType(str, Enum):
    """The message types that can be sent to the agent from the rekuest backend"""

    ASSIGN = "ASSIGN"
    CANCEL = "CANCEL"
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
    EVENT_ACK = "EVENT_ACK"
    ASSIGN_RESPONSE = "ASSIGN_RESPONSE"
    # Caller-bound event-stream mirrors — one per TaskEventKind — streamed back to the
    # participant that originated the task (see ``ExecutionEvent`` and subclasses).
    BOUND_EVENT = "BOUND_EVENT"
    QUEUED_EVENT = "QUEUED_EVENT"
    STARTED_EVENT = "STARTED_EVENT"
    PROGRESS_EVENT = "PROGRESS_EVENT"
    DELEGATE_EVENT = "DELEGATE_EVENT"
    DISCONNECTED_EVENT = "DISCONNECTED_EVENT"
    YIELD_EVENT = "YIELD_EVENT"
    COMPLETED_EVENT = "COMPLETED_EVENT"
    LOG_EVENT = "LOG_EVENT"
    CANCELLING_EVENT = "CANCELLING_EVENT"
    CANCELLED_EVENT = "CANCELLED_EVENT"
    INTERRUPTING_EVENT = "INTERRUPTING_EVENT"
    INTERRUPTED_EVENT = "INTERRUPTED_EVENT"
    PAUSING_EVENT = "PAUSING_EVENT"
    PAUSED_EVENT = "PAUSED_EVENT"
    RESUMING_EVENT = "RESUMING_EVENT"
    RESUMED_EVENT = "RESUMED_EVENT"
    FAILED_EVENT = "FAILED_EVENT"
    CRITICAL_EVENT = "CRITICAL_EVENT"
    # Ack for a caller's lifecycle-control request (cancel/interrupt/pause/resume).
    CONTROL_RESPONSE = "CONTROL_RESPONSE"


class FromAgentMessageType(str, Enum):
    """The message types that can be sent from the agent to the rekuest backend"""

    REGISTER = "REGISTER"
    LOG = "LOG"
    PROGRESS = "PROGRESS"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    YIELD = "YIELD"
    FAILED = "FAILED"
    PAUSED = "PAUSED"
    CRITICAL = "CRITICAL"
    RESUMED = "RESUMED"
    CANCELLED = "CANCELLED"
    APP_CANCELLED = "APP_CANCELLED"  # Cancelled by the app not the user how assigned
    INTERRUPTED = "INTERRUPTED"
    HEARTBEAT_ANSWER = "HEARTBEAT_ANSWER"
    STATE_PATCH = "STATE_PATCH"
    LOCK = "LOCK"
    UNLOCK = "UNLOCK"
    STATE_SNAPSHOT = "STATE_SNAPSHOT"
    SESSION_INIT = "SESSION_INIT"
    ASSIGN_REQUEST = "ASSIGN_REQUEST"
    # Caller-issued lifecycle control requests over the socket (mirroring ASSIGN_REQUEST).
    CANCEL_REQUEST = "CANCEL_REQUEST"
    INTERRUPT_REQUEST = "INTERRUPT_REQUEST"
    PAUSE_REQUEST = "PAUSE_REQUEST"
    RESUME_REQUEST = "RESUME_REQUEST"


class Message(BaseModel):
    """A base message class"""

    # This is the local mapping of the message, reply messages should have the same id
    model_config = ConfigDict(use_enum_values=True, frozen=True)
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class FromAgentEvent(Message):
    """Base for agent→backend reporting events that participate in the ack/resume stream.

    ``seq`` is a monotonic, per-connection stream sequence used only for at-least-once
    **stream** dedup/resume — it is NOT an execution resume cursor (resuming execution
    from a position would require a recorded-effect log, which is deliberately out of
    scope). The backend dedups terminal reports by task id regardless of ``seq``.
    """

    seq: Optional[int] = Field(
        default=None,
        description="Monotonic per-connection stream sequence for at-least-once dedup/resume. Stream-level only — never an execution resume cursor.",
    )


class Assign(Message):
    """An assign call

    And assign call is the initial request to start a specific
    functionality and will have a task id, that will stand
    as a reference for all sub calls (Pause, Interrupt, Reumse, Collect...).
    as well should be passed to all events within the task (
        Progress, Logs, Done, Error, etc)
    )
    """

    type: Literal[ToAgentMessageType.ASSIGN] = ToAgentMessageType.ASSIGN
    interface: str = Field(
        description="The registered interface, that the agent should use to run this task"
    )
    step: bool | None = Field(
        default=None,
        description="Whether to step the task or not (i.e. stop at the first breakpoint and wait for a step message from the rekuest backend to continue). If None don't step.",
    )
    task: str = Field(description="The task id")
    root: Optional[str] = Field(
        default=None,
        description="The root of all cascaded tasks (user triggered task), None if this is the mother",
    )
    """ The mother task (root)"""
    parent: Optional[str] = Field(
        default=None,
        description="The direct parent of this task, None if this is this is the mother",
    )
    """ The parent s"""
    resolution: Optional[str] = Field(
        default=None, description="The resolution id this task has dependencies"
    )
    capture: Optional[bool] = Field(
        default=None, description="Whether to run in debug mode, false by default"
    )
    reference: Optional[str] = Field(
        default=None, description="A reference that the assinger provided"
    )
    args: Dict[str, ShallowJSONSerializable] = Field(
        description="The arguments that was sendend"
    )
    message: Optional[str] = None
    user: str = Field(..., description="The assinging user")
    org: str = Field(description="The org that the user currently belongs to")
    action: str = Field(description="The action of this task")
    implementation: str = Field(
        description="The implementation of this task (the id of the implementation)"
    )
    token: Optional[str] = Field(
        default=None,
        description="An opaque, signed provenance token attesting who caused this task and with which inputs. The agent forwards it untouched to downstream services; it does not validate it. None when the implementation opts out of provenance (needs_token=False).",
    )


class Bounce(Message):
    """A bounce call

    Tells the agent to disconnect and reconnect (a soft restart of the connection).
    Exposed as the ``bounce`` GraphQL mutation. ``duration`` optionally hints how long
    to wait before reconnecting.
    """

    type: Literal[ToAgentMessageType.BOUNCE] = ToAgentMessageType.BOUNCE
    duration: int | None = None


class Kick(Message):
    """A kick call

    Tells the agent to force-disconnect. Unlike ``Bounce`` it will fail and NOT reconnect.
    Exposed as the ``kick`` GraphQL mutation. ``reason`` is an optional human-readable cause.
    """

    type: Literal[ToAgentMessageType.KICK] = ToAgentMessageType.KICK
    reason: str | None = None


class Heartbeat(Message):
    """A heartbeat call
    A heartbeat call tells the agent to send a heartbeat
    and all its children task until a resume is received
    Its on the actor to decide what to do with the children tasks
    """

    type: Literal[ToAgentMessageType.HEARTBEAT] = ToAgentMessageType.HEARTBEAT


class Pause(Message):
    """A pause call

    A pause call tells the agent to pause the task
    and all its children task until a resume is received

    Its on the actor to decide what to do with the children tasks
    (i.e. pause them, cancel them, etc) or to raise an error if the
    state of the assignaiton wouldn't allow this.

    """

    type: Literal[ToAgentMessageType.PAUSE] = ToAgentMessageType.PAUSE
    task: str


class Resume(Message):
    """A resume call

    A resume call unpauses the pause. With ``step=True`` the agent resumes only until the
    next breakpoint (the equivalent of the old standalone step instruction); with
    ``step=False`` it runs on freely."""

    type: Literal[ToAgentMessageType.RESUME] = ToAgentMessageType.RESUME
    task: str
    step: bool = False


class Cancel(Message):
    """A cancel call

    A cancellation call is a request from the user to
    cancel a task nicely (i.e by also nicely
    cancelling all the children tasks).
    Cancel represent a "nice alternative" to the interrupt call.
    While a cancellation of a mother task is only send to
    the mother to kill the children nicely (what the fuck is
    this metaphor), a interrupt will be send to all children
    automatically without the mother.


    Find more information on this in the arkitekt.live
    """

    type: Literal[ToAgentMessageType.CANCEL] = ToAgentMessageType.CANCEL
    task: str


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
    task: str


class Cancelled(FromAgentEvent):
    """A cancelled report

    Sent when the task was successfully cancelled by the actor.
    """

    type: Literal[FromAgentMessageType.CANCELLED] = FromAgentMessageType.CANCELLED
    task: str


class Interrupted(FromAgentEvent):
    """An interrupted report

    Sent when the task was successfully interrupted by the actor.
    """

    type: Literal[FromAgentMessageType.INTERRUPTED] = FromAgentMessageType.INTERRUPTED
    task: str


class Paused(FromAgentEvent):
    """A paused report

    Sent when the task was successfully paused by the actor.
    """

    type: Literal[FromAgentMessageType.PAUSED] = FromAgentMessageType.PAUSED
    task: str


class Resumed(FromAgentEvent):
    """A resumed report

    Sent when the task was successfully resumed by the actor.
    """

    type: Literal[FromAgentMessageType.RESUMED] = FromAgentMessageType.RESUMED
    task: str


class Started(FromAgentEvent):
    """A started report

    Sent when the actor has accepted a task and begun executing it.
    Mirrored to the caller as ``StartedEvent``.
    """

    type: Literal[FromAgentMessageType.STARTED] = FromAgentMessageType.STARTED
    task: str


class Log(FromAgentEvent):
    """A log report

    Sent when the agent wants to send a log message to the rekuest backend.
    """

    type: Literal[FromAgentMessageType.LOG] = FromAgentMessageType.LOG
    task: str
    message: str
    level: LogLevelLiteral = "INFO"
    """The log level of the message"""


class Progress(FromAgentEvent):
    """A progress report

    Sent when the agent wants to report progress on a task.
    """

    type: Literal[FromAgentMessageType.PROGRESS] = FromAgentMessageType.PROGRESS
    task: str
    progress: Optional[int] = None
    message: Optional[str] = None


class Yield(FromAgentEvent):
    """A yield report

    Sent when the agent wants to yield an intermediate result to the rekuest backend.
    """

    type: Literal[FromAgentMessageType.YIELD] = FromAgentMessageType.YIELD
    task: str
    returns: Optional[Dict[str, Any]] = None


class Completed(FromAgentEvent):
    """A completed report

    Sent when the actor has finished the task and all its children tasks.
    """

    type: Literal[FromAgentMessageType.COMPLETED] = FromAgentMessageType.COMPLETED
    task: str


class Failed(FromAgentEvent):
    """A failed report

    Sent when the agent reports a (potentially recoverable) error from execution.
    A ``Critical`` report signals an unrecoverable one instead.
    """

    type: Literal[FromAgentMessageType.FAILED] = FromAgentMessageType.FAILED
    task: str
    error: str


class Critical(FromAgentEvent):
    """A critical report

    Sent when the agent reports an unrecoverable error from execution.
    """

    type: Literal[FromAgentMessageType.CRITICAL] = FromAgentMessageType.CRITICAL
    task: str
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


class SessionInit(Message):
    """A session init message

    A session init message is sent when the agent starts and wants to
    initialize the session with the rekuest backend. This is used to
    send session initialization information from the agent to the rekuest backend
    """

    type: Literal[FromAgentMessageType.SESSION_INIT] = FromAgentMessageType.SESSION_INIT
    session_id: str = Field(
        description="The session id of the agent (generated on a restart of the agent)"
    )
    states: Dict[str, Any] = Field(
        description="A dictionary containing the initial state snapshots, where the key is the state name and the value is the state snapshot"
    )


class StatePatch(Message):
    """A state patch message

    A state patch is sent when the agent wants to send a granular state modification
    to the rekuest backend.
    """

    type: Literal[FromAgentMessageType.STATE_PATCH] = FromAgentMessageType.STATE_PATCH
    session_id: str = Field(
        description="The session id of the agent (generated on a restart of the agent)"
    )
    global_rev: int = Field(description="The global revision of the state")
    state_name: str = Field(description="The name of the state that is being patched")
    ts: float
    op: str
    path: str
    value: Any
    old_value: Any | None = Field(
        description="The old value of the patch, which can be used for debugging and tracing purposes"
    )
    task_id: Optional[str] = Field(
        default=None,
        description="An optional correlation id to correlate this patch with a specific task_id or event in the agent's execution, which can be used for debugging and tracing purposes",
    )


class StateSnapshot(Message):
    """A state snapshot message

    A state snapshot is sent when the agent wants to send a full state snapshot
    to the rekuest backend.
    """

    type: Literal[FromAgentMessageType.STATE_SNAPSHOT] = (
        FromAgentMessageType.STATE_SNAPSHOT
    )
    session_id: str = Field(
        description="The session id of the agent (generated on a restart of the agent)"
    )
    global_rev: int = Field(description="The global revision of the state")
    snapshots: Dict[str, Any] = Field(
        description="A dictionary containing the state snapshots, where the key is the state name and the value is the state snapshot"
    )


class Lock(Message):
    """A lock message

    Sent when the agent wants to acquire a distributed lock on the rekuest backend.
    """

    type: Literal[FromAgentMessageType.LOCK] = FromAgentMessageType.LOCK
    key: str
    task: str


class Unlock(Message):
    """An unlock message

    Sent when the agent wants to release a distributed lock on the rekuest backend.
    """

    type: Literal[FromAgentMessageType.UNLOCK] = FromAgentMessageType.UNLOCK
    key: str


class AssignInquiry(BaseModel):
    """An assign inquiry

    An assign inquiry is a request from rekuest_backend to the agent
    to check the state of a specific task. This is used to check if the
    task is still running or if after a reconnect has died.
    """

    task: str


class Register(Message):
    """A register message

    A register message is sent from the agent to the rekuest backend
    to register the agent with the rekuest backend. This is used to
    register the agent with the rekuest backend and to send the
    agent's token to the rekuest backend.

    """

    type: Literal[FromAgentMessageType.REGISTER] = FromAgentMessageType.REGISTER
    token: str
    force: bool = False
    """If another connection is already registered for this agent, kick it and take over.

    Only honoured for participants that ``executes_work`` (the executor singleton). A
    non-executor (frontend/observer) never force-displaces — its other connections coexist."""
    mode: AgentMode = Field(
        default=AgentMode.EXECUTOR,
        description="How this participant intends to use the protocol. Granted only if the token carries the matching capability scopes; otherwise the connection is closed with MODE_NOT_AUTHORIZED_CODE.",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Per-process identifier minted in-memory by the executor at start-up (never persisted). Its volatility is the reclaim signal: a reconnect with the SAME session_id means the process survived (reclaim in-flight work); a DIFFERENT session_id means a fresh process (fail-and-cascade). Omitted by non-executors.",
    )


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
    agent: str
    inquiries: list[AssignInquiry] = []


class AssignRequest(Message):
    """A caller's request to originate (or resolve) a task over the agent socket.

    This is the WebSocket equivalent of the GraphQL ``assign`` mutation: a participant
    holding ``can_assign_root`` (for a parentless root) or running inside a resolved
    task (for a dependent) asks the backend to create work and dispatch it to an
    executing agent. The fields mirror ``facade.inputs.AssignInputModel``.

    Creation safety is by **idempotency, not transport**: ``reference`` must be stable for
    a logical request, so a resend after reconnect returns the same task (see
    ``AssignResponse``) rather than creating a duplicate.
    """

    type: Literal[FromAgentMessageType.ASSIGN_REQUEST] = (
        FromAgentMessageType.ASSIGN_REQUEST
    )
    reference: str = Field(
        description="Caller-supplied idempotency key. Stable across resends of the same logical request."
    )
    args: Dict[str, ShallowJSONSerializable] = Field(
        default_factory=dict, description="The args of the task (ports → values)."
    )
    action: Optional[str] = Field(
        default=None, description="The action ID to assign to."
    )
    action_hash: Optional[str] = Field(
        default=None, description="The action hash to assign to."
    )
    implementation: Optional[str] = Field(
        default=None, description="A direct implementation ID to assign to."
    )
    agent: Optional[str] = Field(
        default=None, description="A direct agent ID to assign to (with interface)."
    )
    interface: Optional[str] = Field(
        default=None, description="The implementation interface (only with agent)."
    )
    parent: Optional[str] = Field(
        default=None,
        description="The parent task ID. None for a root task (requires can_assign_root).",
    )
    dependency: Optional[str] = Field(
        default=None,
        description="The dependency key to resolve when running inside a resolved task.",
    )
    method: Optional[str] = Field(
        default=None, description="The dependency method to assign."
    )
    resolution: Optional[str] = Field(
        default=None,
        description="The resolution ID for an implementation with dependencies.",
    )
    hooks: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Lifecycle hooks for the task."
    )
    capture: Optional[bool] = Field(
        default=None, description="Whether to run in debug capture mode."
    )
    ephemeral: Optional[bool] = Field(
        default=None, description="Whether the task is ephemeral."
    )
    step: Optional[bool] = Field(
        default=None, description="Whether to step to breakpoints."
    )


class AssignResponse(Message):
    """The backend's authoritative ack that an ``AssignRequest`` was persisted.

    Echoes the originating request id (``request``) and carries the durable task
    id, so the caller can map ``reference``/``request`` → ``task`` BEFORE any
    subsequent task events arrive (those are keyed only by task id). A
    resend of the same ``reference`` yields the same ``task`` with ``created=False``.
    """

    type: Literal[ToAgentMessageType.ASSIGN_RESPONSE] = (
        ToAgentMessageType.ASSIGN_RESPONSE
    )
    request: str = Field(description="The id of the AssignRequest this result answers.")
    reference: str = Field(description="The idempotency key echoed from the request.")
    task: Optional[str] = Field(
        default=None, description="The durable task id, or None when error is set."
    )
    created: bool = Field(
        default=True,
        description="False when an existing task was returned for a duplicate reference.",
    )
    error: Optional[str] = Field(
        default=None,
        description="A human-readable error if the assign was rejected (e.g. missing can_assign_root).",
    )


class ControlRequest(Message):
    """Base for a caller's lifecycle-control request over the socket (cancel/interrupt/…).

    The WebSocket equivalent of the GraphQL postman lifecycle mutations: the caller that
    originated a task drives its lifecycle. The request is two-phase — it broadcasts a
    ToAgent control message and is acked with a ``ControlResponse``; the *outcome*
    (CANCELLED/PAUSED/…) is observed via the ``…Event`` mirror stream, not this ack.
    """

    task: str = Field(description="The task to control (must be owned by this caller).")


class CancelRequest(ControlRequest):
    """Request a graceful cancel of a task."""

    type: Literal[FromAgentMessageType.CANCEL_REQUEST] = (
        FromAgentMessageType.CANCEL_REQUEST
    )
    auto_interrupt: Optional[float] = Field(
        default=None,
        description="Seconds. If the cancel is not confirmed within this window, auto-escalate to an interrupt. None disables escalation (the cancel stays pending until the agent confirms or the caller escalates manually).",
    )


class InterruptRequest(ControlRequest):
    """Request a forceful interrupt (propagates to all children)."""

    type: Literal[FromAgentMessageType.INTERRUPT_REQUEST] = (
        FromAgentMessageType.INTERRUPT_REQUEST
    )


class PauseRequest(ControlRequest):
    """Request the agent to suspend the task."""

    type: Literal[FromAgentMessageType.PAUSE_REQUEST] = (
        FromAgentMessageType.PAUSE_REQUEST
    )


class ResumeRequest(ControlRequest):
    """Request the agent to resume a suspended task.

    ``step=True`` resumes only to the next breakpoint (the equivalent of the old step
    instruction); ``step=False`` runs on freely."""

    type: Literal[FromAgentMessageType.RESUME_REQUEST] = (
        FromAgentMessageType.RESUME_REQUEST
    )
    step: bool = False


class ControlResponse(Message):
    """The backend's ack that a caller lifecycle-control *request* was accepted (or rejected).

    ``accepted`` is True once the request was persisted (an ``-ING`` event) and broadcast to the
    executing agent; False (with ``error``) when rejected — e.g. the task is not owned by
    this caller, is unknown, or is already terminal. The resolved outcome arrives later as a
    ``…Event`` mirror.
    """

    type: Literal[ToAgentMessageType.CONTROL_RESPONSE] = (
        ToAgentMessageType.CONTROL_RESPONSE
    )
    request: str = Field(
        description="The id of the CancelRequest/InterruptRequest/PauseRequest/ResumeRequest this answers."
    )
    task: Optional[str] = Field(default=None, description="The controlled task id.")
    accepted: bool = Field(
        description="True when the request was accepted (broadcast + -ING persisted); False when rejected."
    )
    error: Optional[str] = Field(
        default=None,
        description="A human-readable reason when the request was rejected.",
    )


class EventAck(Message):
    """Backend → agent acknowledgement that a reported event was made durable.

    The agent retains terminal reports (completed/failed/critical/cancelled) until it receives
    the matching ``EventAck`` and resends them on reconnect; this ack (persist-then-ack)
    is what makes that retain-and-resend safe. Correlates by the acked event's id.
    """

    type: Literal[ToAgentMessageType.EVENT_ACK] = ToAgentMessageType.EVENT_ACK
    event: str = Field(description="The id of the FromAgentEvent being acknowledged.")
    task: Optional[str] = Field(
        default=None,
        description="The task the acked event belonged to, for convenience.",
    )
    seq: Optional[int] = Field(
        default=None,
        description="The stream sequence acknowledged, if the event carried one.",
    )


class ExecutionEvent(Message):
    """Base for backend→caller task-event mirrors.

    When a participant originates work (``AssignRequest``), each resulting task
    event is streamed back to it over its own socket as one of the ``…Event`` subclasses
    below — a minimal mirror of the persisted ``TaskEvent``, so the caller never
    needs GraphQL to read results. Delivery is best-effort (the ``task_caller_{caller_id}``
    channel-layer group); on a brief disconnect events are missed and the caller
    re-inquires on reconnect.

    Correlation: ``task`` is the key the caller already learned from
    ``AssignResponse``. ``event`` is the originating ``TaskEvent`` id (a stable
    dedup handle) and ``seq`` its monotonic PK (an ordering / gap-detection key).
    """

    task: str = Field(
        description="The task this event belongs to (the caller's correlation key)."
    )
    event: str = Field(
        description="The originating TaskEvent id — a stable dedup handle."
    )
    seq: int = Field(
        description="The originating TaskEvent's monotonic PK — ordering / gap-detection key."
    )


class BoundEvent(ExecutionEvent):
    """The task was bound to an agent."""

    type: Literal[ToAgentMessageType.BOUND_EVENT] = ToAgentMessageType.BOUND_EVENT


class QueuedEvent(ExecutionEvent):
    """The task was queued."""

    type: Literal[ToAgentMessageType.QUEUED_EVENT] = ToAgentMessageType.QUEUED_EVENT


class StartedEvent(ExecutionEvent):
    """The agent accepted the task and began executing it."""

    type: Literal[ToAgentMessageType.STARTED_EVENT] = ToAgentMessageType.STARTED_EVENT


class ProgressEvent(ExecutionEvent):
    """The executing agent reported progress."""

    type: Literal[ToAgentMessageType.PROGRESS_EVENT] = ToAgentMessageType.PROGRESS_EVENT
    progress: Optional[int] = None
    message: Optional[str] = None


class DelegateEvent(ExecutionEvent):
    """The task was delegated to another task."""

    type: Literal[ToAgentMessageType.DELEGATE_EVENT] = ToAgentMessageType.DELEGATE_EVENT


class DisconnectedEvent(ExecutionEvent):
    """The executing agent disconnected; the task's fate is (for now) unknown."""

    type: Literal[ToAgentMessageType.DISCONNECTED_EVENT] = (
        ToAgentMessageType.DISCONNECTED_EVENT
    )
    message: Optional[str] = None


class YieldEvent(ExecutionEvent):
    """The executing agent yielded a result."""

    type: Literal[ToAgentMessageType.YIELD_EVENT] = ToAgentMessageType.YIELD_EVENT
    returns: Optional[Dict[str, Any]] = None


class CompletedEvent(ExecutionEvent):
    """The task finished successfully."""

    type: Literal[ToAgentMessageType.COMPLETED_EVENT] = (
        ToAgentMessageType.COMPLETED_EVENT
    )


class LogEvent(ExecutionEvent):
    """A log line from the executing agent."""

    type: Literal[ToAgentMessageType.LOG_EVENT] = ToAgentMessageType.LOG_EVENT
    message: Optional[str] = None
    level: LogLevelLiteral = "INFO"


class CancellingEvent(ExecutionEvent):
    """The task is being cancelled."""

    type: Literal[ToAgentMessageType.CANCELLING_EVENT] = (
        ToAgentMessageType.CANCELLING_EVENT
    )


class CancelledEvent(ExecutionEvent):
    """The task was cancelled."""

    type: Literal[ToAgentMessageType.CANCELLED_EVENT] = (
        ToAgentMessageType.CANCELLED_EVENT
    )


class InterruptingEvent(ExecutionEvent):
    """The task is being interrupted."""

    type: Literal[ToAgentMessageType.INTERRUPTING_EVENT] = (
        ToAgentMessageType.INTERRUPTING_EVENT
    )


class InterruptedEvent(ExecutionEvent):
    """The task was interrupted."""

    type: Literal[ToAgentMessageType.INTERRUPTED_EVENT] = (
        ToAgentMessageType.INTERRUPTED_EVENT
    )


class PausingEvent(ExecutionEvent):
    """The task is being paused."""

    type: Literal[ToAgentMessageType.PAUSING_EVENT] = ToAgentMessageType.PAUSING_EVENT


class PausedEvent(ExecutionEvent):
    """The task was paused (suspended)."""

    type: Literal[ToAgentMessageType.PAUSED_EVENT] = ToAgentMessageType.PAUSED_EVENT


class ResumingEvent(ExecutionEvent):
    """The task is being resumed."""

    type: Literal[ToAgentMessageType.RESUMING_EVENT] = ToAgentMessageType.RESUMING_EVENT


class ResumedEvent(ExecutionEvent):
    """The task was resumed (running again)."""

    type: Literal[ToAgentMessageType.RESUMED_EVENT] = ToAgentMessageType.RESUMED_EVENT


class FailedEvent(ExecutionEvent):
    """The task errored (potentially recoverable)."""

    type: Literal[ToAgentMessageType.FAILED_EVENT] = ToAgentMessageType.FAILED_EVENT
    error: Optional[str] = None


class CriticalEvent(ExecutionEvent):
    """The task hit an unrecoverable error."""

    type: Literal[ToAgentMessageType.CRITICAL_EVENT] = ToAgentMessageType.CRITICAL_EVENT
    error: Optional[str] = None


# Every backend→caller mirror, in TaskEventKind order. Imported by ``facade.caller_events``.
ExecutionEventMessage = Union[
    BoundEvent,
    QueuedEvent,
    StartedEvent,
    ProgressEvent,
    DelegateEvent,
    DisconnectedEvent,
    YieldEvent,
    CompletedEvent,
    LogEvent,
    CancellingEvent,
    CancelledEvent,
    InterruptingEvent,
    InterruptedEvent,
    PausingEvent,
    PausedEvent,
    ResumingEvent,
    ResumedEvent,
    FailedEvent,
    CriticalEvent,
]


ToAgentMessage = Union[
    Init,
    Assign,
    Cancel,
    Interrupt,
    Heartbeat,
    Pause,
    Resume,
    Collect,
    ProtocolError,
    Bounce,
    Kick,
    EventAck,
    AssignResponse,
    ControlResponse,
    BoundEvent,
    QueuedEvent,
    StartedEvent,
    ProgressEvent,
    DelegateEvent,
    DisconnectedEvent,
    YieldEvent,
    CompletedEvent,
    LogEvent,
    CancellingEvent,
    CancelledEvent,
    InterruptingEvent,
    InterruptedEvent,
    PausingEvent,
    PausedEvent,
    ResumingEvent,
    ResumedEvent,
    FailedEvent,
    CriticalEvent,
]
FromAgentMessage = Union[
    Critical,
    Log,
    Progress,
    Started,
    Completed,
    Failed,
    Yield,
    Register,
    HeartbeatEvent,
    Resumed,
    Paused,
    Cancelled,
    Interrupted,
    StatePatch,
    StateSnapshot,
    Lock,
    Unlock,
    SessionInit,
    AssignRequest,
    CancelRequest,
    InterruptRequest,
    PauseRequest,
    ResumeRequest,
]
