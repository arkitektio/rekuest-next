"""Base agent class

This is the base class for all agents. It provides the basic functionality
for managing the lifecycle of the actors that are spawned from it.

"""

import random

import asyncio
import copy
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Dict,
    List,
    Optional,
    Self,
    Sequence,
    Type,
    TypeVar,
    cast,
)
import janus
import jsonpatch  # type: ignore[import-untyped]
from pydantic import ConfigDict, Field, PrivateAttr

from koil.composition import KoiledModel
from rekuest_next import messages
from rekuest_next.actors.types import Actor
from rekuest_next.actors.types import Agent as AgentProtocol
from rekuest_next.agents.errors import AgentException, ProvisionException
from rekuest_next.agents.hooks.registry import (
    ShutdownHook,
    StartupHook,
    StartupHookReturns,
)
from rekuest_next.agents.lock import TaskLock
from rekuest_next.app import AppRegistry, get_default_app_registry
from rekuest_next.agents.transport.types import AgentTransport
from rekuest_next.api.schema import (
    Agent,
    Implementation,
    StateDefinitionInput,
    aensure_agent,
    aimplement_agent,
    ashelve,
    aunshelve,
)
from rekuest_next.protocols import AnyState
from rekuest_next.rath import RekuestNextRath
from rekuest_next.scalars import Identifier
from rekuest_next.state.lock import acquired_locks
from rekuest_next.state.publish import Patch
from rekuest_next.state.shrink import ashrink_state
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.structures.serialization.actor import ashrink_return
from rekuest_next.structures.types import JSONSerializable

logger = logging.getLogger(__name__)

# Agent→backend terminal reports. These are retained until the backend acknowledges
# them with an ``EventAck`` (persist-then-ack) and resent on reconnect, mirroring the
# caller-side ``_TERMINAL_TYPES`` in ``agents/caller.py``.
_TERMINAL_FROM_AGENT_TYPES = (
    messages.Completed,
    messages.Failed,
    messages.Critical,
    messages.Cancelled,
    messages.Interrupted,
)

if TYPE_CHECKING:
    from rekuest_next.agents.caller import AgentPostman


class AppContext:
    """Protocol for the app context that is passed to the hooks."""

    __rekuest_app_context__: str


T = TypeVar("T")


def app_context(
    cls: Type[T],
) -> Type[T]:
    """Decorator to register a class as an app context."""

    setattr(cls, "__rekuest_app_context__", cls.__name__)
    return cls


@dataclass
class QueuedPatchEvent:
    interface: str
    patch: Patch
    task_id: Optional[str] = None
    event_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RevisedState:
    """Current agent-owned shrunk state together with its local revision."""

    revision: int
    data: JSONSerializable


class BaseAgent(KoiledModel):
    """Agent

    Agents are the governing entities for every app. They are responsible for
    managing the lifecycle of the direct actors that are spawned from them through arkitekt.

    Agents are nothing else than actors in the classic distributed actor model, but they are
    always provided when the app starts and they do not provide functionality themselves but rather
    manage the lifecycle of the actors that are spawned from them.

    The actors that are spawned from them are called guardian actors and they are the ones that+
    provide the functionality of the app. These actors can then in turn spawn other actors that
    are not guardian actors. These actors are called non-guardian actors and their lifecycle is
    managed by the guardian actors that spawned them. This allows for a hierarchical structure
    of actors that can be spawned from the agents.


    """

    name: str | None = Field(
        default=None,
        description="The name of the agent. This is used to identify the agent in the system.",
    )

    # TODO: KV Store
    shelve: Dict[str, Any] = Field(default_factory=dict)  # kv_store -> Seperate
    transport: AgentTransport
    app_registry: AppRegistry = Field(default_factory=get_default_app_registry)

    contexts: Dict[str, Any] = Field(
        default_factory=dict,
        description="Maps context keys to context values registed with @context",
    )
    states: Dict[str, AnyState] = Field(
        default_factory=dict,
        description="Maps the state key to the state value. This is used to store the states of the agent.",
    )
    locks: Dict[str, TaskLock] = Field(default_factory=dict)

    capture_condition: asyncio.Condition = Field(default_factory=asyncio.Condition)
    capture_active: bool = Field(default=False)

    managed_actors: Dict[str, Actor] = Field(default_factory=dict)

    interface_implementation_map: Dict[str, Implementation] = Field(
        default_factory=dict
    )

    managed_assignments: Dict[str, messages.Assign] = Field(default_factory=dict)
    running_assignments: Dict[str, str] = Field(
        default_factory=dict, description="Maps task to actor id"
    )

    managed_actor_tasks: Dict[str, asyncio.Task[None]] = Field(
        default_factory=dict,
        description="Maps actor id to the task that is running the actor",
    )
    _errorfuture: Optional[asyncio.Future[Exception]] = None
    _agent: Optional[Agent] = None

    _current_shrunk_states: Dict[str, JSONSerializable] = PrivateAttr(
        default_factory=lambda: {}  # type: ignore[return-value]
    )
    _app_context: Optional[AppContext] = PrivateAttr(default=None)
    _caller_postman: Optional["AgentPostman"] = PrivateAttr(default=None)
    """The agent-as-caller postman, lazily built. Bound as ``current_postman`` while an
    actor body runs so actor-internal ``acall``/``acall_dependency`` route over this socket."""

    _connected_event: asyncio.Event = PrivateAttr(default_factory=asyncio.Event)
    """Set when the server acknowledges the agent (an ``Init`` message is received)."""
    _receiver: Optional[AsyncIterator[messages.ToAgentMessage]] = PrivateAttr(
        default=None
    )
    """The live transport message stream, shared between ``aconnect`` and ``aloop``."""

    _interface_stateschema_input_map: Dict[str, StateDefinitionInput] = PrivateAttr(
        default_factory=lambda: {}  # typ
    )

    _background_tasks: Dict[str, asyncio.Task[None]] = PrivateAttr(
        default_factory=lambda: {}
    )
    _collected_state_schemas: Dict[str, StateDefinitionInput] = PrivateAttr(
        default_factory=lambda: {}
    )
    _collected_startup_hooks: Dict[str, StartupHook] = PrivateAttr(
        default_factory=lambda: {}
    )
    _collected_shutdown_hooks: Dict[str, ShutdownHook] = PrivateAttr(
        default_factory=lambda: {}
    )
    _collected_background_workers: Dict[str, Any] = PrivateAttr(
        default_factory=lambda: {}
    )
    _ran_startup_hooks: bool = PrivateAttr(default=False)
    """Set once the startup hooks have run, so teardown only runs the shutdown hooks
    for an agent that actually started (and only once per start)."""

    # Event based necessities
    current_session: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="A unique identifier for the current session. This is used to group patches and snapshots that belong to the same logical session together. By default an agent start a new session when booting up",
    )
    _event_queue: janus.Queue[QueuedPatchEvent] | None = PrivateAttr(default=None)
    _patch_processor_task: asyncio.Task[None] | None = PrivateAttr(default=None)
    _event_seq: int = PrivateAttr(default=0)
    # message id -> retained terminal event awaiting its EventAck (insertion-ordered dict)
    _unacked_events: Dict[str, messages.FromAgentMessage] = PrivateAttr(
        default_factory=dict
    )
    global_revision: int = 0
    snapshot_interval: int = Field(
        default=60,
        description="How many persisted patches should elapse before all current shrunk states are checkpointed.",
    )
    teardown_join_timeout: float = Field(
        default=5.0,
        description="Maximum seconds to wait for queued state patches to flush during teardown before closing the patch queue anyway. Bounds teardown so it can never hang on an unconsumed patch.",
    )
    cancel_grace_period: float = Field(
        default=5.0,
        description="Maximum seconds to wait for the message-consumer task to unwind when the agent loop is cancelled before proceeding to teardown anyway. Bounds cancellation so it can never hang on a stream that ignores cancellation.",
    )
    shutdown_hook_timeout: float = Field(
        default=20.0,
        description="Maximum seconds a single shutdown hook may run during teardown before it is abandoned. Bounds teardown so it can never hang on a hook that does not return.",
    )
    started: bool = False
    running: bool = False
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def caller_postman(self) -> "AgentPostman":
        """The agent-as-caller postman (lazily built).

        Bound as ``current_postman`` while an actor body runs so that actor-internal
        ``acall``/``acall_dependency`` originate work over this agent's socket instead of
        through the GraphQL postman.
        """
        if self._caller_postman is None:
            from rekuest_next.agents.caller import AgentPostman

            self._caller_postman = AgentPostman(self)
        return self._caller_postman

    async def alock(self, key: str, task: str) -> None:
        """Signal that a task has acquired a lock."""
        return None

    async def aunlock(self, key: str) -> None:
        """Signal that a task has released a lock."""
        return None

    async def aget_read_only_proxy(self, key: str) -> AnyState:
        """Acquire a read-only state proxy for a given key."""
        return self.states[key]

    async def aget_write_proxy(self, key: str) -> AnyState:
        """Acquire a write state proxy for a given key."""
        return self.states[key]

    async def apatch_event_loop(self) -> None:
        """Patch the event loop to process queued patches in order."""
        if self._event_queue is None:
            raise AgentException("Patch queue is not initialized")

        try:
            logger.debug("Starting patch event loop")
            while True:
                queued_patch = await self._event_queue.async_q.get()
                try:
                    await self._aprocess_patch_event(queued_patch)
                finally:
                    self._event_queue.async_q.task_done()
        except asyncio.CancelledError:
            logger.debug("Patch event loop cancelled, shutting down")
            raise

    def publish_patch(
        self, interface: str, patch: Patch, task_id: str | None = None
    ) -> None:
        """Publish a patch to the agent. This is used to publish patches to the
        agent from the actor."""

        if self._event_queue is None:
            raise AgentException("Patch queue is not initialized")
        self._event_queue.sync_q.put(
            QueuedPatchEvent(interface=interface, patch=patch, task_id=task_id)
        )

    async def _aprocess_patch_event(self, queued_patch: QueuedPatchEvent) -> None:
        interface = queued_patch.interface
        patch = queued_patch.patch

        # Check the revisions of the state
        future_global_rev = self.global_revision + 1

        # Enforce that patches are applied in order
        if interface not in self._current_shrunk_states:
            self._current_shrunk_states[interface] = await self.ashrink_state(
                interface=interface,
                state=self.states[interface],
            )

        shrunk_value = await self._ashrink_patch_value(interface, patch)

        self._aapply_patch_to_shrunk_state(interface, patch, shrunk_value)

        self.global_revision = future_global_rev
        if self.global_revision % self.snapshot_interval == 0:
            await self.apublish_snapshot(
                messages.StateSnapshot(
                    session_id=self.current_session,
                    global_rev=self.global_revision,
                    snapshots={
                        interface: copy.deepcopy(shrunk_state)
                        for interface, shrunk_state in self._current_shrunk_states.items()
                    },
                )
            )

        await self.apublish_patch(
            messages.StatePatch(
                global_rev=self.global_revision,
                state_name=interface,
                ts=queued_patch.event_time.timestamp(),
                op=patch.op,
                path=patch.path,
                value=shrunk_value,
                old_value=None,
                task_id=patch.correlation_id,
                session_id=self.current_session,
            ),
        )

    async def _ashrink_patch_value(
        self, interface: str, patch: Patch
    ) -> JSONSerializable | None:
        if patch.op not in ("add", "replace"):
            return None

        if patch.port is None:
            raise AgentException(f"No state schema found for interface {interface}")

        structure_registry = self.get_structure_registry_for_interface(interface)
        return await ashrink_return(patch.port, patch.value, structure_registry, self)

    def _aapply_patch_to_shrunk_state(
        self,
        interface: str,
        patch: Patch,
        shrunk_value: JSONSerializable | None,
    ) -> None:
        patch_document: dict[str, JSONSerializable] = {
            "op": patch.op,
            "path": patch.path,
        }
        if patch.op != "remove":
            patch_document["value"] = shrunk_value

        jsonpatch.apply_patch(
            self._current_shrunk_states[interface],
            [patch_document],
            in_place=True,
        )

    async def acollect(self, key: str) -> None:
        raise NotImplementedError("Collect method is not implemented in BaseAgent")

    async def _acreate_session(self) -> str:
        """Create a new session identifier. Returns a UUID by default; override in subclasses."""
        return str(uuid.uuid4())

    def get_locks_for_keys(self, keys: Sequence[str]) -> List[TaskLock]:
        """Get the locks for the given keys.

        Args:
            keys: The keys to get the locks for.
        Returns:
            The list of locks for the given keys.
        """
        return [self.locks[key] for key in keys if key in self.locks]

    def collect_from_extensions(self) -> None:
        """Collect state schemas, hooks, sync keys and locks from the app registry.

        The actual implementation/state/blok payload is assembled (and validated)
        lazily by ``AppRegistry.to_implement_agent_input`` at registration time; this
        only populates the runtime bookkeeping the agent needs while running.
        """
        app_registry = self.app_registry

        # Collect state schemas
        for interface, schema in app_registry.states.items():
            self._collected_state_schemas[interface] = schema.definition

        # Collect startup hooks, shutdown hooks and background workers
        for name, hook in app_registry.hooks_registry.startup_hooks.items():
            self._collected_startup_hooks[name] = hook
        for name, shutdown_hook in app_registry.hooks_registry.shutdown_hooks.items():
            self._collected_shutdown_hooks[name] = shutdown_hook
        for name, worker in app_registry.hooks_registry.background_worker.items():
            self._collected_background_workers[name] = worker

        # Build the runtime task locks
        for lock_schema in app_registry.get_locks():
            if lock_schema.key not in self.locks:
                self.locks[lock_schema.key] = TaskLock(self, lock_schema)

    def get_structure_registry_for_interface(self, interface: str) -> StructureRegistry:
        """Get the structure registry for a given interface from extensions.

        Args:
            interface: The interface to get the registry for.

        Returns:
            The structure registry for the interface.
        """

        try:
            return self.app_registry.get_registry_for_interface(interface)
        except (KeyError, AssertionError):
            raise AgentException(
                f"No structure registry found for interface {interface}"
            )

    async def ashelve(
        self,
        identifier: Identifier,
        resource_id: str,
        label: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        raise NotImplementedError("ashelve not implemented in BaseAgent")

    async def aput_on_shelve(
        self,
        identifier: Identifier,
        value: Any,  # noqa: ANN401
    ) -> str:  # noqa: ANN401
        """Get the shelve for the agent. This is used to get the shelve
        for the agent and all the actors that are spawned from it.
        """

        if hasattr(value, "aget_label"):
            label = await value.aget_label()
        else:
            label = None

        if hasattr(value, "aget_description"):
            description = await value.aget_description()
        else:
            description = None

        if not label:
            label = str(value)

        drawer_id = await self.ashelve(
            identifier=identifier,
            resource_id=uuid.uuid4().hex,
            label=label,
            description=description,
        )

        self.shelve[drawer_id] = value

        return drawer_id

    async def aget_from_shelve(self, key: str) -> Any:  # noqa: ANN401
        """Get a value from the shelve. This is used to get values from the
        shelve for the agent and all the actors that are spawned from it.
        """
        assert key in self.shelve, "Drawer is not in current shelve"
        return self.shelve[key]

    async def process(self, message: messages.ToAgentMessage) -> None:
        """Processes a message from the transport. This is used to process
        messages that are sent to the agent from the transport. The agent will
        then send the message to the actors.
        """
        logger.info(f"Agent received {message}")

        # TODO: Should be a match statement, as we have dropepd support for python 3.9,

        if isinstance(message, messages.Init):
            # The Init message is the server's acknowledgement of our Register.
            # Signal that the agent is connected so callers awaiting aconnect()
            # can proceed.
            self._connected_event.set()
            # Reconnect (the backend re-sends Init after a transient drop): resend any
            # terminal reports we retained but never saw acked. Sent as-is (not via
            # _adispatch) so seq is preserved and they are not re-buffered; the backend
            # dedups terminal reports by task id.
            for retained in list(self._unacked_events.values()):
                await self.transport.asend(retained)
            for inquiry in message.inquiries:
                if inquiry.task in self.managed_assignments:
                    assignment = self.managed_assignments[inquiry.task]
                    actor = self.managed_actors[assignment.interface]

                    # Checking status
                    status = await actor.acheck_task(assignment.task)
                    if status:
                        await self._adispatch(
                            messages.Progress(
                                task=inquiry.task,
                                message="Actor is still running",
                                progress=0,
                            )
                        )
                    else:
                        await self._adispatch(
                            messages.Critical(
                                task=inquiry.task,
                                error="The assignment was not running anymore. But the actor was still managed. This could lead to some race conditions",
                            )
                        )
                else:
                    await self._adispatch(
                        messages.Critical(
                            task=inquiry.task,
                            error="After disconnect actor was no longer managed (probably the app was restarted)",
                        )
                    )

        elif isinstance(message, messages.Assign):
            if message.interface in self.managed_actors:
                # The actor is already spawned
                actor = self.managed_actors[message.interface]
                self.managed_assignments[message.task] = message
                await actor.apass(message)
            else:
                try:
                    actor = await self.aspawn_actor_from_assign(message)
                    await actor.apass(message)

                except Exception as e:
                    await self._adispatch(
                        messages.Critical(
                            task=message.task,
                            error=f"Not able to create actor through extensions {str(e)}",
                        )
                    )
                    raise e

        elif isinstance(
            message,
            (
                messages.Cancel,
                messages.Pause,
                messages.Resume,
            ),
        ):
            if message.task in self.managed_assignments:
                assignment = self.managed_assignments[message.task]
                actor = self.managed_actors[assignment.interface]
                await actor.apass(message)
            else:
                logger.warning(
                    "Received unassignation for a provision that is not running. "
                    f"Received: {message.task}"
                )
                await self._adispatch(
                    messages.Critical(
                        task=message.task,
                        error="Actors is no longer running and not managed. Probablry there was a restart",
                    )
                )

        elif isinstance(message, messages.ProtocolError):
            raise AgentException(
                "Received a protocol error from the backend. This usually means "
                f"the agent sent a message the backend could not process: {message.error}"
            )

        elif isinstance(message, messages.AssignResponse):
            self.caller_postman.handle_assign_response(message)

        elif isinstance(message, messages.ControlResponse):
            self.caller_postman.handle_control_response(message)

        elif isinstance(message, messages.ExecutionEvent):
            # Base of every backend→caller `…Event` mirror. Routed to the caller postman
            # so an actor-internal acall/acall_dependency can observe the work it delegated.
            self.caller_postman.handle_execution_event(message)

        elif isinstance(message, messages.Collect):
            for key in message.drawers:
                await self.acollect(key)

        elif isinstance(message, messages.AssignInquiry):
            if message.task in self.managed_assignments:
                assignment = self.managed_assignments[message.task]
                actor = self.managed_actors[assignment.interface]

                # Checking status
                status = await actor.acheck_task(assignment.task)
                if status:
                    await self._adispatch(
                        messages.Progress(
                            task=message.task,
                            message="Actor is still running",
                        )
                    )
                else:
                    await self._adispatch(
                        messages.Critical(
                            task=message.task,
                            error="The assignment was not running anymore. But the actor was still managed. This could lead to some race conditions",
                        )
                    )
            else:
                await self._adispatch(
                    messages.Critical(
                        task=message.task,
                        error="After disconnect actor was no longer managed (probably the app was restarted)",
                    )
                )

        elif isinstance(message, messages.EventAck):
            # Backend made the reported event durable; stop retaining it.
            self._unacked_events.pop(message.event, None)

        else:
            raise AgentException(f"Unknown message type {type(message)}")

    async def atear_down(self) -> None:
        """Tears down the agent. This is used to tear down the agent
        and all the actors that are spawned from it.
        """
        logger.info("Tearing down the agent")

        for background_task in list(self._background_tasks.values()):
            background_task.cancel()

        for background_task in list(self._background_tasks.values()):
            try:
                await background_task
            except asyncio.CancelledError:
                pass

        # Runs while the patch processor, the queue and the transport are still
        # alive, so a hook that touches state still gets its patches flushed by the
        # bounded join below.
        await self.arun_shutdown_hooks()

        if self._event_queue is not None:
            # Best-effort flush of queued patches before stopping the processor.
            # Bounded by a timeout so teardown can never hang on a patch that was
            # enqueued but will not be consumed (e.g. published during shutdown).
            try:
                await asyncio.wait_for(
                    self._event_queue.async_q.join(), timeout=self.teardown_join_timeout
                )
            except (RuntimeError, asyncio.TimeoutError):
                logger.warning(
                    "Timed out flushing queued patches during teardown; "
                    "closing the patch queue anyway"
                )

        if self._patch_processor_task is not None:
            self._patch_processor_task.cancel()
            try:
                await self._patch_processor_task
            except (asyncio.CancelledError, RuntimeError):
                pass

        if self._event_queue is not None:
            try:
                await self._event_queue.aclose()
            except RuntimeError:
                pass
            self._event_queue = None

        for actor_task in self.managed_actor_tasks.values():
            actor_task.cancel()
        # just stopping the actor, not cancelling the provision..

        for actor_task in self.managed_actor_tasks.values():
            try:
                await actor_task
            except asyncio.CancelledError:
                pass

        if self._errorfuture is not None and not self._errorfuture.done():
            self._errorfuture.cancel()
            try:
                await self._errorfuture
            except asyncio.CancelledError:
                pass

        await self.astop_background()
        await self.transport.adisconnect()

        # Reset the connected signal and stored receiver so a subsequent run of a
        # re-entered agent waits for a fresh Init instead of observing stale state.
        self._connected_event.clear()
        self._receiver = None

    async def aget_hash(self) -> str:
        """Get the hash of the agent. This is used to identify the agent in the system and to check if the agent has changed."""
        # TODO: Actually perform the hashing based on the extensions and their implementations, state schemas, and other relevant information. For now, we just return a random hash to force the agent to register all implementations on every start.
        return random.randbytes(16).hex()

    async def _adispatch(self, message: messages.FromAgentMessage) -> None:
        """Assign a stream seq to events, retain terminal reports for ack, then send.

        Every agent→backend event flows through here so it gets a monotonic ``seq``
        and so terminal reports (completed/failed/critical/cancelled/interrupted) are
        retained in ``_unacked_events`` until the backend confirms durability with an
        ``EventAck`` (handled in ``process``) — the persist-then-ack contract.
        """
        if isinstance(message, messages.FromAgentEvent):
            self._event_seq += 1
            # Messages are frozen, so produce a copy carrying the assigned seq.
            message = message.model_copy(update={"seq": self._event_seq})
            if isinstance(message, _TERMINAL_FROM_AGENT_TYPES):
                self._unacked_events[message.id] = message
        await self.transport.asend(message)

    async def asend(self, actor: "Actor", message: messages.FromAgentMessage) -> None:
        """Sends a message to the actor. This is used for sending messages to the
        agent from the actor. The agent will then send the message to the transport.
        """
        logger.debug(
            f"Agent forwarding {message.id} from actor {actor.__class__.__name__}"
        )
        await self._adispatch(message)

    async def ashrink_state(self, interface: str, state: AnyState) -> Any:  # noqa: ANN401
        """Shrink the state to the schema. This will be called when the agent starts"""
        if interface not in self._interface_stateschema_input_map:
            raise AgentException(f"State {interface} not found in agent {self.name}")

        schema = self._interface_stateschema_input_map[interface]
        structure_registry = self.get_structure_registry_for_interface(interface)

        # Shrink the value to the schema
        shrinked_state = await ashrink_state(
            state,
            schema,
            structure_reg=structure_registry,
            shelver=self,
        )
        return shrinked_state

    async def ainit_states(
        self, hook_return: StartupHookReturns, app_context: Any = None
    ) -> None:  # noqa: ANN401
        """Initialize the state of the agent. This will be called when the agent starts"""

        state_schemas = self._collected_state_schemas
        missing_initializers = sorted(
            interface
            for interface in state_schemas
            if interface not in hook_return.states
        )
        if missing_initializers:
            missing_states = ", ".join(missing_initializers)
            raise AgentException(
                "Registered states are missing initialization values from startup hooks: "
                f"{missing_states}"
            )

        for interface, startup_value in hook_return.states.items():
            # Set the actual state value

            self.states[interface] = startup_value

            # Set the state schema that is needed to shrink the state
            self._interface_stateschema_input_map[interface] = state_schemas[interface]

            initial_shrunk_state = await self.ashrink_state(
                interface=interface,
                state=startup_value,
            )

            self._current_shrunk_states[interface] = copy.deepcopy(initial_shrunk_state)

        # TODO: Implement state initialization through dataclass

        snapshot_event = messages.StateSnapshot(
            session_id=self.current_session,
            global_rev=self.global_revision,
            snapshots={
                interface: copy.deepcopy(shrunk_state)
                for interface, shrunk_state in self._current_shrunk_states.items()
            },
        )
        logger.debug("Publishing initial snapshot event: %s ", snapshot_event)
        await self.apublish_snapshot(snapshot_event)

    async def apublish_patch(self, patch: messages.StatePatch) -> None:
        """Publish a patch to the agent.  Will forward the patch to the transport"""
        raise NotImplementedError("apublish_envelope not implemented in BaseAgent")

    async def apublish_snapshot(self, snapshot: messages.StateSnapshot) -> None:
        """Publish a snapshot to the agent.  Will forward the snapshot to the transport"""
        raise NotImplementedError("apublish_snapshot not implemented in BaseAgent")

    # Agent Related Getters
    async def aget_context(self, context: str) -> Any:  # noqa: ANN401
        """Get a context from the agent. This is used to get contexts from the
        agent from the actor."""
        if context not in self.contexts:
            raise AgentException(f"Context {context} not found in agent {self.name}")
        return self.contexts[context]

    async def arun_background(self) -> None:
        """Run the background tasks. This will be called when the agent starts."""

        for name, worker in self._collected_background_workers.items():
            task = asyncio.create_task(
                worker.arun(self, contexts=self.contexts, states=self.states)
            )
            task.add_done_callback(
                lambda task, name=name: self._on_background_done(name, task)
            )
            self._background_tasks[name] = task

    def _on_background_done(self, name: str, task: "asyncio.Task[None]") -> None:
        """Done-callback for background worker tasks. Removes the task from the
        registry and logs any genuine failure (ignoring cancellation)."""
        self._background_tasks.pop(name, None)
        if task.cancelled():
            return
        exception = task.exception()
        if exception is not None:
            logger.error("Worker %s failed with exception: %s", name, exception)

    async def astop_background(self) -> None:
        """Stop the background tasks. This will be called when the agent stops."""
        for _, task in self._background_tasks.items():
            task.cancel()

        try:
            await asyncio.gather(
                *self._background_tasks.values(), return_exceptions=True
            )
        except asyncio.CancelledError:
            pass

    async def arun_startup_hooks(
        self, app_context: Optional[AppContext] = None
    ) -> StartupHookReturns:
        """Run all startup hooks collected from extensions.

        Returns:
            StartupHookReturns: The combined states and contexts from all hooks.
        """
        from rekuest_next.agents.hooks.errors import StartupHookError

        states: Dict[str, Any] = {}
        contexts: Dict[str, Any] = {}

        for key, hook in self._collected_startup_hooks.items():
            try:
                answer = await asyncio.wait_for(
                    hook.arun(app_context=app_context),
                    timeout=20,
                )
                for i in answer.states:
                    if i in states:
                        raise StartupHookError(f"State {i} already defined")
                    states[i] = answer.states[i]

                for i in answer.contexts:
                    if i in contexts:
                        raise StartupHookError(f"Context {i} already defined")
                    contexts[i] = answer.contexts[i]

            except Exception as e:
                raise StartupHookError(f"Startup hook {key} failed") from e

        return StartupHookReturns(states=states, contexts=contexts)

    async def arun_shutdown_hooks(self) -> None:
        """Run all shutdown hooks collected from extensions.

        Runs in the reverse of the registration order, so teardown unwinds what
        startup set up. Only runs for an agent that got as far as its startup
        hooks, and only once per start. A hook that fails or times out is logged
        and the remaining hooks still run: teardown must never fail because of a
        shutdown hook.
        """
        from rekuest_next.agents.hooks.errors import ShutdownHookError

        if not self._ran_startup_hooks:
            return
        self._ran_startup_hooks = False

        for key, hook in reversed(list(self._collected_shutdown_hooks.items())):
            try:
                await asyncio.wait_for(
                    hook.arun(
                        agent=cast("AgentProtocol", self),
                        contexts=self.contexts,
                        states=self.states,
                        app_context=self._app_context,
                    ),
                    timeout=self.shutdown_hook_timeout,
                )
            except Exception as e:
                hook_error = ShutdownHookError(f"Shutdown hook {key} failed")
                hook_error.__cause__ = e
                logger.error(hook_error, exc_info=hook_error)

    async def aensure(self) -> None:
        """A function that gets called so that we create the agent with its definitions before we start the ooop"""

    async def astart(self, app_context: Optional[AppContext] = None) -> None:
        """Starts the agent. This is used to start the agent and all the actors
        that are spawned from it. The agent will then start the transport and
        start listening for messages from the transport.
        """
        # Collect state schemas, startup hooks, and background workers from all extensions
        self.collect_from_extensions()

        await self.aensure()
        self.current_session = await self._acreate_session()

        # Run startup hooks from extensions

        # Inspect all locks
        locks = [lock.lock_key for lock in self.locks.values()]

        with acquired_locks(*locks):
            hook_return = await self.arun_startup_hooks(app_context=app_context)
            # From here on the app has set up resources, so teardown owes it the
            # shutdown hooks (even if the rest of the startup fails).
            self._ran_startup_hooks = True
            await self.ainit_states(hook_return=hook_return, app_context=app_context)

        self.global_revision = 0
        self._event_queue = janus.Queue()
        self._patch_processor_task = asyncio.create_task(self.apatch_event_loop())
        self._patch_processor_task.add_done_callback(
            lambda x: (
                logger.error(f"Patch processor task failed: {x.exception()}")
                if not x.cancelled() and x.exception() is not None
                else None
            )
        )

        for context_key, context_value in hook_return.contexts.items():
            self.contexts[context_key] = context_value

        await self.arun_background()
        self._errorfuture = asyncio.Future()

    async def aspawn_actor_from_assign(self, assign: messages.Assign) -> Actor:
        """Spawns an Actor from a Assign.

        We only spawn actors on assign as some actors can be meta actors that
        do not exist hardcoded in the agent extensions, but rather are created
        on demand based on the assign message.

        """

        try:
            actor_builder = self.app_registry.get_builder_for_interface(
                assign.interface
            )
        except KeyError:
            raise ProvisionException(
                f"No actor builder found for interface {assign.interface} in agent {self.name}"
            )

        actor = actor_builder(agent=self)

        self.managed_actors[assign.interface] = actor
        self.managed_assignments[assign.task] = assign

        return actor

    async def _adrain_until_connected(self) -> None:
        """Process incoming messages until the server acknowledges the agent.

        Returns as soon as an ``Init`` message has been handled (which sets
        ``_connected_event``), leaving the transport stream live for ``aloop``.
        """
        assert self._receiver is not None, "Receiver must be set before draining"
        if self._connected_event.is_set():
            return
        async for message in self._receiver:
            await self.process(message)
            if self._connected_event.is_set():
                return

    async def _await_acknowledged(self) -> None:
        """Wait until the server has acknowledged the agent.

        For the websocket transport this drains the message stream until an
        ``Init`` is received. Subclasses whose transport has no acknowledgement
        handshake (e.g. the server-side FastAPI transport) override this.
        """
        await self._adrain_until_connected()

    async def _aconnect_sequence(self, context: Optional[AppContext] = None) -> None:
        """The startup + transport-open + acknowledge sequence, unbounded.

        Each phase is logged so that a stall (when ``aconnect`` wraps this in a
        timeout) points to the exact phase that hung.
        """
        logger.debug("aconnect: running astart")
        await self.astart(app_context=context)
        logger.debug("aconnect: opening transport")
        self._receiver = self.transport.areceive().__aiter__()
        await self.transport.aconnect()
        logger.debug("aconnect: draining until acknowledged")
        await self._await_acknowledged()
        logger.info("Agent connected and acknowledged by the server")

    async def aconnect(
        self,
        context: Optional[AppContext] = None,
        timeout: float | None = None,
    ) -> None:
        """Starts the agent and connects to the transport.

        This runs the startup phase, opens the transport, and returns once the
        server has acknowledged the agent (an ``Init`` message is received). The
        message stream is left live so that ``aloop`` can resume consuming it.

        The whole sequence (including ``astart``) is bounded by ``timeout``: if it
        does not complete within that many seconds, ``asyncio.TimeoutError`` is
        raised and the agent is torn down.
        """
        self._app_context = context

        try:
            sequence = self._aconnect_sequence(context=context)
            if timeout is not None:
                await asyncio.wait_for(sequence, timeout)
            else:
                await sequence
        except BaseException:
            logger.error("Agent failed to connect", exc_info=True)
            await self.atear_down()
            raise

    async def _aconsume_messages(self) -> None:
        """Resume the transport stream and process every message it yields."""
        assert self._receiver is not None, "aconnect() must run before aloop()"
        async for message in self._receiver:
            await self.process(message)

    async def aloop(self) -> None:
        """Async loop that processes messages after the agent has connected.

        The transport stream is consumed in a dedicated child task. This keeps
        cancellation responsive: some streams (e.g. a websocket mid-close) do not
        promptly honour cancellation, which would otherwise leave ``aloop`` stuck
        in the "cancelling" state forever and never run teardown. On cancellation
        we cancel the consumer, wait for it only up to ``cancel_grace_period``,
        and then always tear down.
        """
        self.running = True
        consume_task = asyncio.ensure_future(self._aconsume_messages())
        try:
            # Shield so that cancelling ``aloop`` returns control here immediately
            # instead of blocking on ``consume_task`` (which may be stuck unwinding
            # a stream that ignores cancellation). We then stop it with a bound.
            await asyncio.shield(consume_task)
        except asyncio.CancelledError:
            logger.info(f"Provisioning task cancelled. We are running {self.transport}")
            self.running = False
            await self._astop_consume_task(consume_task)
            await self.atear_down()
            raise
        except Exception as e:
            logger.error(f"Error in agent loop: {str(e)}")
            await self._astop_consume_task(consume_task)
            await self.atear_down()
            raise e

    async def _astop_consume_task(self, consume_task: "asyncio.Task[None]") -> None:
        """Stop the message-consumer task, bounded by ``cancel_grace_period``.

        The transport is deliberately left connected: teardown still publishes
        (shutdown hooks, final state patches), and those messages need a live
        socket. ``atear_down`` disconnects at the end, once everything is out.

        Only if the consumer refuses to unwind do we disconnect early to release a
        stream that ignores cancellation, so teardown can never hang on it.
        """
        if consume_task.done():
            return
        consume_task.cancel()
        try:
            await asyncio.wait_for(
                asyncio.shield(consume_task), timeout=self.cancel_grace_period
            )
            return
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        except Exception:
            logger.warning("Message consumer errored during shutdown", exc_info=True)
            return

        if consume_task.done():
            return

        logger.warning(
            "Message consumer did not unwind in time; disconnecting the transport to "
            "release it. Messages queued during teardown may be lost."
        )
        try:
            await self.transport.adisconnect()
        except Exception:
            logger.warning("Transport disconnect during shutdown failed", exc_info=True)
        try:
            await asyncio.wait_for(
                asyncio.shield(consume_task), timeout=self.cancel_grace_period
            )
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        except Exception:
            logger.warning("Message consumer errored during shutdown", exc_info=True)

    async def aprovide(self, context: Optional[AppContext] = None) -> None:
        """Provides the agent.

        This starts the agent, connects to the transport, and then listens for
        messages from the transport. It is simply ``aconnect`` followed by
        ``aloop``.
        """
        try:
            logger.info("Launching provisioning task.")
            await self.aconnect(context=context)
            await self.aloop()
        except asyncio.CancelledError:
            logger.info("Provisioning task cancelled. We are running")
            await self.atear_down()
            raise

    async def __aenter__(self) -> Self:
        """Enter the agent context manager. This is used to enter the agent

        context manager and start the agent. The agent will then start the
        transport and start listening for messages from the transport.
        """

        await self.transport.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Exit the agent.

        This method is called when the agent is exited. It is responsible for
        tearing down the agent and all the actors that are spawned from it.

        Args:
            exc_type (Optional[type]): The type of the exception
            exc_val (Optional[Exception]): The exception value
            exc_tb (Optional[type]): The traceback

        """
        await self.atear_down()
        await self.transport.__aexit__(exc_type, exc_val, exc_tb)


class RekuestAgent(BaseAgent):
    """The Rekuest Agent

    This is the default agent that is used by rekuest. It provides the basic
    functionality for managing the lifecycle of the actors that are spawned
    from it.

    """

    rath: RekuestNextRath = Field(
        description="The graph client that is used to make queries to when connecting to the rekuest server.",
    )

    pass

    async def aensure(self) -> None:
        """Register all implementations that are handled by extensiosn

        This method is called by the agent when it starts and it is responsible for
        registering the templates that are defined in the extensions.
        """

        self._agent = await aensure_agent(
            name=self.name,
            rath=self.rath,
        )

        if self._agent.hash != await self.aget_hash():
            logger.info(
                "Agent hash does not match, registering implementations and states again"
            )
            # Assemble + validate the whole agent input from the app registry
            # (the ImplementAgentInput model validators fire on construction).
            agent_input = self.app_registry.to_implement_agent_input(
                name=self.name,
            )
            agent = await aimplement_agent(
                name=agent_input.name,
                implementations=agent_input.implementations,
                states=agent_input.states,
                locks=agent_input.locks,
                bloks=agent_input.bloks,
                rath=self.rath,
            )

            logger.info("Registered agent with id %s and hash %s", agent.id, agent.hash)

    async def ashelve(
        self,
        identifier: Identifier,
        resource_id: str,
        label: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        drawer = await ashelve(
            identifier=identifier,
            resource_id=resource_id,
            label=label,
            description=description,
            rath=self.rath,
        )
        return drawer.id

    async def acollect(self, key: str) -> None:
        del self.shelve[key]
        await aunshelve(id=key, rath=self.rath)

    async def apublish_snapshot(self, snapshot: messages.StateSnapshot) -> None:
        await self.transport.asend(snapshot)
        logger.debug("Published snapshot %s", snapshot)
        return None

    async def apublish_patch(self, patch: messages.StatePatch) -> None:
        await self.transport.asend(patch)
        logger.debug("Published patch %s", patch)
        return None
