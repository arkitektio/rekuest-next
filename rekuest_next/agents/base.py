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
from typing import Any, Dict, Generic, List, Optional, Self, Type, TypeVar
import janus
import jsonpatch  # type: ignore[import-untyped]
from pydantic import ConfigDict, Field, PrivateAttr

from koil import unkoil
from koil.composition import KoiledModel
from rekuest_next import messages
from rekuest_next.actors.sync import SyncKeyManager
from rekuest_next.actors.types import Actor, Passport
from rekuest_next.agents.errors import AgentException, ProvisionException
from rekuest_next.agents.hooks.registry import StartupHook, StartupHookReturns
from rekuest_next.agents.lock import TaskLock
from rekuest_next.agents.registry import (
    ExtensionRegistry,
    get_default_extension_registry,
)
from rekuest_next.agents.transport.types import AgentTransport
from rekuest_next.api.schema import (
    Agent,
    Implementation,
    StateDefinitionInput,
    LockImplementationInput,
    ImplementationInput,
    StateImplementationInput,
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


ContextType = TypeVar("ContextType", bound="AppContext")


@dataclass
class QueuedPatchEvent:
    interface: str
    patch: Patch
    assignation_id: Optional[str] = None
    event_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RevisedState:
    """Current agent-owned shrunk state together with its local revision."""

    revision: int
    data: JSONSerializable


class BaseAgent(KoiledModel, Generic[ContextType]):
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
    instance_id: str = Field(
        default="default",
        description="The instance id of the agent. This is used to identify the agent in the system.",
    )

    # TODO: KV Store
    shelve: Dict[str, Any] = Field(default_factory=dict)  # kv_store -> Seperate
    transport: AgentTransport
    extension_registry: ExtensionRegistry = Field(
        default_factory=get_default_extension_registry
    )

    contexts: Dict[str, Any] = Field(
        default_factory=dict,
        description="Maps context keys to context values registed with @context",
    )
    states: Dict[str, AnyState] = Field(
        default_factory=dict,
        description="Maps the state key to the state value. This is used to store the states of the agent.",
    )
    locks: Dict[str, TaskLock] = Field(default_factory=dict)

    # TODO: Probably dead
    capture_condition: asyncio.Condition = Field(default_factory=asyncio.Condition)
    capture_active: bool = Field(default=False)

    managed_actors: Dict[str, Actor] = Field(default_factory=dict)

    interface_implementation_map: Dict[str, Implementation] = Field(
        default_factory=dict
    )
    implementation_interface_map: Dict[str, str] = Field(default_factory=dict)
    provision_passport_map: Dict[int, Passport] = Field(default_factory=lambda: {})

    managed_assignments: Dict[str, messages.Assign] = Field(default_factory=dict)
    running_assignments: Dict[str, str] = Field(
        default_factory=dict, description="Maps assignation to actor id"
    )

    # TODO Delete
    sync_key_manager: SyncKeyManager = Field(
        default_factory=SyncKeyManager,
        description="Manager for sync key locks across all implementations",
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

    _shrunk_states: Dict[str, Any] = PrivateAttr(default_factory=lambda: {})
    _interface_stateschema_map: Dict[str, StateDefinitionInput] = PrivateAttr(
        default_factory=lambda: {}  # typ
    )
    _interface_stateschema_input_map: Dict[str, StateDefinitionInput] = PrivateAttr(
        default_factory=lambda: {}  # typ
    )

    _background_tasks: Dict[str, asyncio.Task[None]] = PrivateAttr(
        default_factory=lambda: {}
    )
    _collected_state_schemas: Dict[str, StateDefinitionInput] = PrivateAttr(
        default_factory=lambda: {}
    )
    _collected_structure_registries: Dict[str, Any] = PrivateAttr(
        default_factory=lambda: {}
    )
    _collected_startup_hooks: Dict[str, StartupHook] = PrivateAttr(
        default_factory=lambda: {}
    )
    _collected_background_workers: Dict[str, Any] = PrivateAttr(
        default_factory=lambda: {}
    )
    _state_class_interface_map: Dict[type, str] = PrivateAttr(
        default_factory=lambda: {}
    )

    # Event based necessities
    current_session: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="A unique identifier for the current session. This is used to group patches and snapshots that belong to the same logical session together. By default an agent start a new session when booting up",
    )
    _event_queue: janus.Queue[QueuedPatchEvent] | None = PrivateAttr(default=None)
    _patch_processor_task: asyncio.Task[None] | None = PrivateAttr(default=None)
    global_revision: int = 0
    snapshot_interval: int = Field(
        default=60,
        description="How many persisted patches should elapse before all current shrunk states are checkpointed.",
    )
    started: bool = False
    running: bool = False
    model_config = ConfigDict(arbitrary_types_allowed=True)

    _collected_implementations: List[ImplementationInput] = PrivateAttr(
        default_factory=lambda: []
    )
    _collected_states: list[StateImplementationInput] = PrivateAttr(
        default_factory=lambda: []
    )
    _collected_locks: list[LockImplementationInput] = PrivateAttr(
        default_factory=lambda: []
    )

    def model_post_init(self, __context: Any) -> None:
        pass

    async def alock(self, key: str, assignation: str) -> None:
        """Signal that an assignation has acquired a lock."""
        return None

    async def aunlock(self, key: str) -> None:
        """Signal that an assignation has released a lock."""
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
        self, interface: str, patch: Patch, assignation_id: str | None = None
    ) -> None:
        """Publish a patch to the agent. This is used to publish patches to the
        agent from the actor."""

        if self._event_queue is None:
            raise AgentException("Patch queue is not initialized")
        self._event_queue.sync_q.put(
            QueuedPatchEvent(
                interface=interface, patch=patch, assignation_id=assignation_id
            )
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
                messages.StateSnapshotEvent(
                    session_id=self.current_session,
                    global_rev=self.global_revision,
                    snapshots={
                        interface: copy.deepcopy(shrunk_state)
                        for interface, shrunk_state in self._current_shrunk_states.items()
                    },
                )
            )

        await self.apublish_patch(
            messages.StatePatchEvent(
                global_rev=self.global_revision,
                state_name=interface,
                ts=queued_patch.event_time.timestamp(),
                op=patch.op,
                path=patch.path,
                value=shrunk_value,
                old_value=None,
                correlation_id=patch.correlation_id,
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

    def get_locks_for_keys(self, keys: List[str]) -> List[TaskLock]:
        """Get the locks for the given keys.

        Args:
            keys: The keys to get the locks for.
        Returns:
            The list of locks for the given keys.
        """
        locks: List[TaskLock] = []
        for key in keys:
            for lock in self.locks.values():
                if lock.lock_key == key:
                    locks.append(lock)
        return locks

    def collect_from_extensions(self) -> None:
        """Collect state schemas, startup hooks, background workers, and sync keys from all extensions.

        This method iterates through all registered extensions and collects their
        state schemas, startup hooks, background workers, and sync keys into the agent's
        internal collections.
        """

        for extension in self.extension_registry.agent_extensions.values():
            # Collect state schemas
            state_schemas = extension.get_states()
            for interface, schema in state_schemas.items():
                self._collected_state_schemas[interface] = schema.definition
                self._collected_states.append(schema)

            # Collect startup hooks
            startup_hooks = extension.get_startup_hooks()
            for name, hook in startup_hooks.items():
                self._collected_startup_hooks[name] = hook

            # Collect background workers
            background_workers = extension.get_background_workers()
            for name, worker in background_workers.items():
                self._collected_background_workers[name] = worker

            # Collect sync keys from implementations
            implementations = extension.get_implementations()
            for implementation in implementations:
                if implementation.locks is not None:
                    self.sync_key_manager.register_sync_keys(
                        implementation.interface or implementation.definition.name,
                        implementation.locks,
                    )

                self._collected_implementations.append(implementation)

            locks = extension.get_lock_schemas()
            for interface, lock_schema in locks.items():
                if interface not in self.locks:
                    self.locks[interface] = TaskLock(self, lock_schema)

    def get_structure_registry_for_interface(self, interface: str) -> StructureRegistry:
        """Get the structure registry for a given interface from extensions.

        Args:
            interface: The interface to get the registry for.

        Returns:
            The structure registry for the interface.
        """

        for extension in self.extension_registry.agent_extensions.values():
            app_registry = getattr(extension, "app_registry", None)
            if app_registry is not None:
                return app_registry.state_registry.get_registry_for_interface(interface)
        raise AgentException(f"No structure registry found for interface {interface}")

    def get_interface_for_state_class(self, cls: type) -> str:
        """Get the interface for a state class from extensions.

        Args:
            cls: The state class to get the interface for.

        Returns:
            The interface name for the state class.
        """
        for extension in self.extension_registry.agent_extensions.values():
            app_registry = getattr(extension, "app_registry", None)
            if app_registry is not None:
                try:
                    return app_registry.state_registry.get_interface_for_class(cls)
                except (KeyError, AssertionError):
                    continue
        raise AgentException(f"No interface found for state class {cls}")

    async def ashelve(
        self,
        instance_id: str,
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
            instance_id=self.instance_id,
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

        if isinstance(message, messages.Init):
            for inquiry in message.inquiries:
                if inquiry.assignation in self.managed_assignments:
                    assignment = self.managed_assignments[inquiry.assignation]
                    actor = self.managed_actors[assignment.actor_id]

                    # Checking status
                    status = await actor.acheck_assignation(assignment.assignation)
                    if status:
                        await self.transport.asend(
                            messages.ProgressEvent(
                                assignation=inquiry.assignation,
                                message="Actor is still running",
                                progress=0,
                            )
                        )
                    else:
                        await self.transport.asend(
                            messages.CriticalEvent(
                                assignation=inquiry.assignation,
                                error="The assignment was not running anymore. But the actor was still managed. This could lead to some race conditions",
                            )
                        )
                else:
                    await self.transport.asend(
                        messages.CriticalEvent(
                            assignation=inquiry.assignation,
                            error="After disconnect actor was no longer managed (probably the app was restarted)",
                        )
                    )

        elif isinstance(message, messages.Assign):
            if message.actor_id in self.managed_actors:
                # The actor is already spawned
                actor = self.managed_actors[message.actor_id]
                self.managed_assignments[message.assignation] = message
                await actor.apass(message)
            else:
                try:
                    actor = await self.aspawn_actor_from_assign(message)
                    await actor.apass(message)

                except Exception as e:
                    await self.transport.asend(
                        messages.CriticalEvent(
                            assignation=message.assignation,
                            error=f"Not able to create actor through extensions {str(e)}",
                        )
                    )
                    raise e

        elif isinstance(
            message,
            (
                messages.Cancel,
                messages.Step,
                messages.Pause,
                messages.Resume,
            ),
        ):
            if message.assignation in self.managed_assignments:
                assignment = self.managed_assignments[message.assignation]
                actor = self.managed_actors[assignment.actor_id]
                await actor.apass(message)
            else:
                logger.warning(
                    "Received unassignation for a provision that is not running"
                    f"Managed: {self.provision_passport_map} Received: {message.assignation}"
                )
                await self.transport.asend(
                    messages.CriticalEvent(
                        assignation=message.assignation,
                        error="Actors is no longer running and not managed. Probablry there was a restart",
                    )
                )

        elif isinstance(message, messages.Collect):
            for key in message.drawers:
                await self.acollect(key)

        elif isinstance(message, messages.AssignInquiry):
            if message.assignation in self.managed_assignments:
                assignment = self.managed_assignments[message.assignation]
                actor = self.managed_actors[assignment.actor_id]

                # Checking status
                status = await actor.acheck_assignation(assignment.assignation)
                if status:
                    await self.transport.asend(
                        messages.ProgressEvent(
                            assignation=message.assignation,
                            message="Actor is still running",
                        )
                    )
                else:
                    await self.transport.asend(
                        messages.CriticalEvent(
                            assignation=message.assignation,
                            error="The assignment was not running anymore. But the actor was still managed. This could lead to some race conditions",
                        )
                    )
            else:
                await self.transport.asend(
                    messages.CriticalEvent(
                        assignation=message.assignation,
                        error="After disconnect actor was no longer managed (probably the app was restarted)",
                    )
                )

        else:
            raise AgentException(f"Unknown message type {type(message)}")

    async def atear_down(self) -> None:
        """Tears down the agent. This is used to tear down the agent
        and all the actors that are spawned from it.
        """
        logger.info("Tearing down the agent")

        for background_task in self._background_tasks.values():
            background_task.cancel()

        for background_task in self._background_tasks.values():
            try:
                await background_task
            except asyncio.CancelledError:
                pass

        if self._event_queue is not None:
            try:
                await self._event_queue.async_q.join()
            except RuntimeError:
                pass
            try:
                await self._event_queue.aclose()
            except RuntimeError:
                pass
            self._event_queue = None

        if self._patch_processor_task is not None:
            self._patch_processor_task.cancel()
            try:
                await self._patch_processor_task
            except (asyncio.CancelledError, RuntimeError):
                pass

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

        for extension in self.extension_registry.agent_extensions.values():
            await extension.atear_down()

        await self.astop_background()
        await self.transport.adisconnect()

    async def aget_hash(self) -> str:
        """Get the hash of the agent. This is used to identify the agent in the system and to check if the agent has changed."""
        # TODO: Actually perform the hashing based on the extensions and their implementations, state schemas, and other relevant information. For now, we just return a random hash to force the agent to register all implementations on every start.
        return random.randbytes(16).hex()

    async def asend(self, actor: "Actor", message: messages.FromAgentMessage) -> None:
        """Sends a message to the actor. This is used for sending messages to the
        agent from the actor. The agent will then send the message to the transport.
        """
        logger.debug(
            f"Agent forwarding {message.id} from actor {actor.__class__.__name__}"
        )
        await self.transport.asend(message)

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

        if not self.instance_id:
            raise AgentException("Instance id is not set. The agent is not initialized")

        state_schemas = self._collected_state_schemas

        for interface, startup_value in hook_return.states.items():
            # Set the actual state value

            config = startup_value.__rekuest_state_config__
            self.states[interface] = startup_value

            # Set the state schema that is needed to shrink the state
            self._interface_stateschema_input_map[interface] = state_schemas[interface]

            initial_shrunk_state = await self.ashrink_state(
                interface=interface,
                state=startup_value,
            )

            self._current_shrunk_states[interface] = copy.deepcopy(initial_shrunk_state)

        snapshot_event = messages.StateSnapshotEvent(
            session_id=self.current_session,
            global_rev=self.global_revision,
            snapshots={
                interface: copy.deepcopy(shrunk_state)
                for interface, shrunk_state in self._current_shrunk_states.items()
            },
        )
        logger.debug("Publishing initial snapshot event: %s ", snapshot_event)
        await self.apublish_snapshot(snapshot_event)

    async def apublish_patch(self, patch: messages.StatePatchEvent) -> None:
        """Publish a patch to the agent.  Will forward the patch to the transport"""
        raise NotImplementedError("apublish_envelope not implemented in BaseAgent")

    async def apublish_snapshot(self, snapshot: messages.StateSnapshotEvent) -> None:
        """Publish a snapshot to the agent.  Will forward the snapshot to the transport"""
        raise NotImplementedError("apublish_snapshot not implemented in BaseAgent")

    # Agent Related Getters
    async def aget_context(self, context: str) -> Any:  # noqa: ANN401
        """Get a context from the agent. This is used to get contexts from the
        agent from the actor."""
        if context not in self.contexts:
            raise AgentException(f"Context {context} not found in agent {self.name}")
        return self.contexts[context]

    def get_context_for_type(self, context: Type[ContextType]) -> ContextType:  # noqa: ANN401
        """Get a context from the agent. This is used to get contexts from the
        agent from the actor."""
        from rekuest_next.agents.context import get_context_name, is_context

        if not self.running:
            raise AgentException(
                "Agent is not running. Contexts are not available yet."
            )

        if is_context(context):
            context_name = get_context_name(context)
            return self.contexts[context_name]

        raise AgentException(
            f"Context for type {context} not found in agent {self.name}"
        )

    async def aget_app_context(self) -> AppContext:
        """Get the app context from the agent. This is used to get the
        app context from the agent."""
        if self._app_context is None:
            raise AgentException("App context is not set in the agent")
        return self._app_context

    async def aget_state(self, interface: str) -> AnyState:
        """Get the state of the extension. This will be called when"""
        if interface not in self.states:
            raise AgentException(f"State {interface} not found in agent {self.name}")
        return self.states[interface]

    def get_sync_keys_for_interface(self, interface: str) -> tuple[str, ...]:
        """Get the sync keys for a given interface.

        Args:
            interface: The interface name.

        Returns:
            A tuple of sync key names, or empty tuple if none.
        """
        for extension in self.extension_registry.agent_extensions.values():
            implementations = extension.get_implementations()
            for impl in implementations:
                if (impl.interface or impl.definition.name) == interface:
                    return impl.locks or ()
        return ()

    def get_sync_key_status(self) -> list[dict]:
        """Get the status of all sync keys.

        Returns:
            A list of status dictionaries for all sync key locks.
        """
        return self.sync_key_manager.get_all_status()

    async def arun_background(self) -> None:
        """Run the background tasks. This will be called when the agent starts."""

        for name, worker in self._collected_background_workers.items():
            task = asyncio.create_task(
                worker.arun(self, contexts=self.contexts, states=self.states)
            )
            task.add_done_callback(lambda x: self._background_tasks.pop(name))
            task.add_done_callback(
                lambda x: logger.error(
                    "Worker %s failed with exception: %s", name, x.exception()
                )
            )
            self._background_tasks[name] = task

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
        self, instance_id: str, app_context: Optional[ContextType] = None
    ) -> StartupHookReturns:
        """Run all startup hooks collected from extensions.

        Args:
            instance_id: The instance id of the agent.

        Returns:
            StartupHookReturns: The combined states and contexts from all hooks.
        """
        from rekuest_next.agents.hooks.errors import StartupHookError

        states: Dict[str, Any] = {}
        contexts: Dict[str, Any] = {}

        for key, hook in self._collected_startup_hooks.items():
            try:
                answer = await asyncio.wait_for(
                    hook.arun(instance_id=instance_id, app_context=app_context),
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

    async def aensure(self) -> None:
        """A function that gets called so that we create the agent with its definitions before we start the ooop"""

    async def astart(
        self, instance_id: str, app_context: Optional[ContextType] = None
    ) -> None:
        """Starts the agent. This is used to start the agent and all the actors
        that are spawned from it. The agent will then start the transport and
        start listening for messages from the transport.
        """
        # Collect state schemas, startup hooks, and background workers from all extensions
        self.collect_from_extensions()

        state = await self.aensure()
        self.current_session = await self._acreate_session()

        # Run startup hooks from extensions

        # Inspect all locks
        locks = [lock.lock_key for lock in self.locks.values()]

        with acquired_locks(*locks):
            hook_return = await self.arun_startup_hooks(
                instance_id=instance_id, app_context=app_context
            )
            await self.ainit_states(hook_return=hook_return, app_context=app_context)

        self.global_revision = 0
        self._event_queue = janus.Queue()
        self._patch_processor_task = asyncio.create_task(self.apatch_event_loop())
        self._patch_processor_task.add_done_callback(
            lambda x: logger.error(f"Patch processor task failed: {x.exception()}")
        )

        for extension in self.extension_registry.agent_extensions.values():
            await extension.astart(instance_id=instance_id, app_context=app_context)

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

        if assign.extension not in self.extension_registry.agent_extensions:
            raise ProvisionException(
                f"Extension {assign.extension} not found in agent {self.name}"
            )
        extension = self.extension_registry.agent_extensions[assign.extension]

        actor = await extension.aspawn_actor_for_interface(self, assign.interface)

        self.managed_actors[assign.actor_id] = actor
        self.managed_assignments[assign.assignation] = assign

        return actor

    async def await_errorfuture(self) -> Exception:
        """Waits for the error future to be set. This is used to wait for"""
        if self._errorfuture is None:
            raise AgentException("Error future is not set")

        return await self._errorfuture

    def provide(self, context: Optional[ContextType] = None) -> None:
        """Provides the agent. This starts the agents and
        connected the transport."""
        return unkoil(self.aprovide, context=context)

    async def aloop(self) -> None:
        """Async loop that runs the agent. This is used to run the agent"""
        try:
            self.running = True
            await self.transport.aconnect(self.instance_id)

            async for message in self.transport.areceive():
                await self.process(message)
        except asyncio.CancelledError:
            logger.info(f"Provisioning task cancelled. We are running {self.transport}")
            self.running = False
            await self.atear_down()
            raise
        except Exception as e:
            logger.error(f"Error in agent loop: {str(e)}")
            await self.atear_down()
            raise e

    async def aprovide(self, context: Optional[ContextType] = None) -> None:
        """Provides the agent.

        This starts the agents and connectes to the transport.
        It also starts the agent and starts listening for messages from the transport.
        """
        if hasattr(context, "instance_id"):
            self.instance_id = getattr(context, "instance_id", self.instance_id)

        self._app_context = context

        try:
            logger.info(
                f"Launching provisioning task. We are running {self.instance_id}"
            )
            await self.astart(
                instance_id=self.instance_id, app_context=self._app_context
            )
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


class RekuestAgent(BaseAgent[ContextType]):
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
            instance_id=self.instance_id,
            name=self.name,
        )

        if self._agent.hash != await self.aget_hash():
            logger.info(
                "Agent hash does not match, registering implementations and states again"
            )
            agent = await aimplement_agent(
                instance_id=self.instance_id,
                name=self.name,
                implementations=self._collected_implementations,
                states=self._collected_states,
                locks=self._collected_locks,
            )

            logger.info("Registered agent with id %s and hash %s", agent.id, agent.hash)

    async def ashelve(
        self,
        instance_id: str,
        identifier: Identifier,
        resource_id: str,
        label: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        drawer = await ashelve(
            instance_id=instance_id,
            identifier=identifier,
            resource_id=resource_id,
            label=label,
            description=description,
            rath=self.rath,
        )
        return drawer.id

    async def acollect(self, key: str) -> None:
        del self.shelve[key]
        await aunshelve(instance_id=self.instance_id, id=key, rath=self.rath)

    async def apublish_snapshot(self, snapshot: messages.StateSnapshotEvent) -> None:
        await self.transport.asend(snapshot)
        logger.debug("Published snapshot %s", snapshot)
        return None

    async def apublish_patch(self, patch: messages.StatePatchEvent) -> None:
        await self.transport.asend(patch)
        logger.debug("Published patch %s", patch)
        return None
