"""FastAPI agent transport and websocket helpers.

The FastAPI integration exposes three scoped websocket channels:

- task updates via `TaskConnectionManager`
- state updates via `StateConnectionManager`
- lock updates via `LockConnectionManager`

Outgoing agent messages are routed into one of those channels based on the
message type so each websocket stream only receives the events it is meant to
carry.
"""

import asyncio
import copy
import logging
from types import TracebackType
from typing import Any, AsyncIterator, Callable, Generic, List, Optional, Self, TypeVar
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ConfigDict, Field, PrivateAttr

from rekuest_next import messages
from rekuest_next.agents.base import BaseAgent
from rekuest_next.agents.transport.base import AgentTransport
from rekuest_next.api.schema import StateImplementationInput, StateSchemaInput
from rekuest_next.contrib.fastapi.models import (
    LockView,
    StateCollectionResponse,
    StateView,
    TaskCollectionResponse,
    TaskView,
)

logger = logging.getLogger(__name__)


def _is_state_message(message: messages.FromAgentMessage) -> bool:
    """Return whether a message belongs to the state update stream."""
    return isinstance(message, messages.StatePatchEvent)


def _is_lock_message(message: messages.FromAgentMessage) -> bool:
    """Return whether a message belongs to the lock update stream."""
    return isinstance(message, (messages.LockEvent, messages.UnlockEvent))


def _task_routing_key(message: messages.FromAgentMessage) -> str | None:
    """Resolve a default task routing key from a task-scoped message."""
    if _is_state_message(message) or _is_lock_message(message):
        return None
    return getattr(message, "assignation", None)


def _state_routing_key(message: messages.FromAgentMessage) -> str | None:
    """Resolve the state name used for state websocket subscriptions."""
    if not isinstance(message, messages.StatePatchEvent):
        return None
    return message.envelope.state_name


def _lock_routing_key(message: messages.FromAgentMessage) -> str | None:
    """Resolve the lock key used for lock websocket subscriptions."""
    if not isinstance(message, (messages.LockEvent, messages.UnlockEvent)):
        return None
    return message.key


class _ScopedConnectionManager:
    """Manage websocket connections for a single routed update stream.

    Each manager holds a set of active websocket clients together with their
    optional subscriptions. Subclasses define how a routing key is derived from
    an outgoing agent message.
    """

    def __init__(self) -> None:
        """Initialize empty connection and subscription registries."""
        self._active_connections: set[WebSocket] = set()
        self._subscriptions: dict[WebSocket, set[str] | None] = {}
        self._lock = asyncio.Lock()

    def get_routing_key(self, message: messages.FromAgentMessage) -> str | None:
        """Resolve the subscription key for a message.

        Returning `None` means the message does not belong to this stream and
        will not be delivered by this manager.

        Args:
            message: The outgoing agent message.
        """
        raise NotImplementedError

    async def connect(
        self,
        websocket: WebSocket,
        subscriptions: set[str] | None = None,
    ) -> None:
        """Accept and register a websocket with optional subscriptions.

        Args:
            websocket: The websocket connection to register.
            subscriptions: Optional routing keys the websocket wants to receive.
        """
        await websocket.accept()
        async with self._lock:
            self._active_connections.add(websocket)
            self._subscriptions[websocket] = subscriptions
        logger.info(f"WebSocket connected. Total connections: {len(self._active_connections)}")

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a websocket connection and its subscriptions.

        Args:
            websocket: The websocket connection to remove.
        """
        async with self._lock:
            self._active_connections.discard(websocket)
            self._subscriptions.pop(websocket, None)
        logger.info(f"WebSocket disconnected. Total connections: {len(self._active_connections)}")

    async def broadcast_model(self, message: messages.FromAgentMessage) -> None:
        """Broadcast a model message to subscribed websocket clients.

        Args:
            message: The outgoing agent message to distribute.
        """
        routing_key = self.get_routing_key(message)
        if routing_key is None:
            return

        message_json = message.model_dump_json()
        async with self._lock:
            disconnected: List[WebSocket] = []
            for connection in self._active_connections:
                subscriptions = self._subscriptions.get(connection)
                if subscriptions is not None and routing_key not in subscriptions:
                    continue
                try:
                    await connection.send_text(message_json)
                except Exception as e:
                    logger.warning(f"Failed to send message to WebSocket: {e}")
                    disconnected.append(connection)

            for conn in disconnected:
                self._active_connections.discard(conn)
                self._subscriptions.pop(conn, None)

    async def send_personal(self, websocket: WebSocket, message: str) -> None:
        """Send a raw message to one websocket client.

        Args:
            websocket: The target websocket connection.
            message: The JSON message payload.
        """
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.warning(f"Failed to send personal message to WebSocket: {e}")

    @property
    def connection_count(self) -> int:
        """Return the number of active connections."""
        return len(self._active_connections)


class TaskConnectionManager(_ScopedConnectionManager):
    """Connection manager for task-scoped websocket subscriptions."""

    def __init__(self) -> None:
        """Initialize a task websocket manager."""
        super().__init__()
        self.routing_key_resolver: Callable[[messages.FromAgentMessage], str | None] | None = None

    def get_routing_key(self, message: messages.FromAgentMessage) -> str | None:
        """Return the task routing key for an outgoing message."""
        if self.routing_key_resolver is not None:
            return self.routing_key_resolver(message)
        return _task_routing_key(message)


class StateConnectionManager(_ScopedConnectionManager):
    """Connection manager for state-scoped websocket subscriptions."""

    def get_routing_key(self, message: messages.FromAgentMessage) -> str | None:
        """Return the state name for state patch messages."""
        return _state_routing_key(message)


class LockConnectionManager(_ScopedConnectionManager):
    """Connection manager for lock-scoped websocket subscriptions."""

    def get_routing_key(self, message: messages.FromAgentMessage) -> str | None:
        """Return the lock key for lock lifecycle messages."""
        return _lock_routing_key(message)


class FastApiTransport(AgentTransport):
    """Transport for FastAPI-based agents.

    This transport accepts incoming command messages from HTTP routes through
    `asubmit()` and forwards outgoing agent messages into one of three scoped
    websocket streams: tasks, states, or locks.
    """

    task_connection_manager: TaskConnectionManager = Field(
        default_factory=TaskConnectionManager,
        description="The WebSocket connection manager for task updates.",
    )
    state_connection_manager: StateConnectionManager = Field(
        default_factory=StateConnectionManager,
        description="The WebSocket connection manager for state updates.",
    )
    lock_connection_manager: LockConnectionManager = Field(
        default_factory=LockConnectionManager,
        description="The WebSocket connection manager for lock updates.",
    )

    _receive_queue: Optional[asyncio.Queue[messages.ToAgentMessage]] = PrivateAttr(default=None)
    _connected: bool = PrivateAttr(default=False)
    _instance_id: Optional[str] = PrivateAttr(default=None)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def connected(self) -> bool:
        """Return True if the transport is connected."""
        return self._connected

    async def asubmit(self, message: messages.ToAgentMessage) -> str:
        """Submit a message to the agent from an API route.

        This method is called from FastAPI route handlers to send messages
        to the agent for processing. Responses are sent via WebSocket.

        Args:
            message: The message to send to the agent.

        Returns:
            The assignation ID for tracking the request.
        """
        if self._receive_queue is None:
            raise RuntimeError("Transport not connected. Call aconnect first.")

        # Put the message on the queue for the agent to process
        await self._receive_queue.put(message)
        logger.info(f"Submitted message to agent: {message}")

        # Return the assignation ID for tracking
        if isinstance(message, messages.Assign):
            return message.assignation
        return getattr(message, "assignation", getattr(message, "id", "unknown"))

    async def asend(self, message: messages.FromAgentMessage) -> None:
        """Route an outgoing agent message to its websocket stream.

        Message routing is based on message type:

        - `StatePatchEvent` -> state websocket manager
        - `LockEvent` and `UnlockEvent` -> lock websocket manager
        - every other outgoing message -> task websocket manager

        Args:
            message: The message to send to the appropriate websocket stream.
        """
        message_json = message.model_dump_json()
        logger.info(f"Agent sending message: {message_json}")

        if _is_state_message(message):
            await self.state_connection_manager.broadcast_model(message)
            return

        if _is_lock_message(message):
            await self.lock_connection_manager.broadcast_model(message)
            return

        await self.task_connection_manager.broadcast_model(message)

    async def aconnect(self, instance_id: str) -> None:
        """Connect the transport.

        Args:
            instance_id: The instance ID for this agent.
        """
        self._instance_id = instance_id
        self._receive_queue = asyncio.Queue()
        self._connected = True
        logger.info(f"FastAPI transport connected with instance_id: {instance_id}")

    async def areceive(self) -> AsyncIterator[messages.ToAgentMessage]:
        """Receive messages from the queue.

        This is an async generator that yields messages as they arrive
        in the receive queue (submitted via API routes).

        Yields:
            Messages to be processed by the agent.
        """
        if self._receive_queue is None:
            raise RuntimeError("Transport not connected. Call aconnect first.")

        while True:
            try:
                message = await self._receive_queue.get()
                yield message
            except asyncio.CancelledError:
                logger.info("Receive loop cancelled")
                raise

    async def adisconnect(self) -> None:
        """Disconnect the transport."""
        self._connected = False
        self._receive_queue = None
        logger.info("FastAPI transport disconnected")

    async def _handle_scoped_websocket(
        self,
        websocket: WebSocket,
        connection_manager: _ScopedConnectionManager,
        subscriptions: set[str] | None = None,
        initial_message: dict[str, Any] | None = None,
    ) -> None:
        """Serve a websocket that listens to one routed manager.

        Args:
            websocket: The accepted websocket connection.
            connection_manager: The scoped manager responsible for this stream.
            subscriptions: Optional set of routing keys to filter delivered events.
            initial_message: Optional initial payload sent immediately after connect.
        """
        await connection_manager.connect(websocket, subscriptions=subscriptions)
        if initial_message is not None:
            await websocket.send_json(initial_message)
        try:
            while True:
                await websocket.receive()
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            await connection_manager.disconnect(websocket)

    async def handle_task_websocket(
        self,
        websocket: WebSocket,
        action_keys: set[str] | None = None,
        initial_message: dict[str, Any] | None = None,
    ) -> None:
        """Handle a task websocket connection filtered by action keys.

        Args:
            websocket: The websocket connection to serve.
            action_keys: Optional action keys to subscribe to.
            initial_message: Optional initial snapshot sent after connect.
        """
        await self._handle_scoped_websocket(
            websocket,
            self.task_connection_manager,
            subscriptions=action_keys,
            initial_message=initial_message,
        )

    async def handle_state_websocket(
        self,
        websocket: WebSocket,
        state_keys: set[str] | None = None,
        initial_message: dict[str, Any] | None = None,
    ) -> None:
        """Handle a state websocket connection filtered by state keys.

        Args:
            websocket: The websocket connection to serve.
            state_keys: Optional state keys to subscribe to.
            initial_message: Optional initial snapshot sent after connect.
        """
        await self._handle_scoped_websocket(
            websocket,
            self.state_connection_manager,
            subscriptions=state_keys,
            initial_message=initial_message,
        )

    async def handle_lock_websocket(
        self,
        websocket: WebSocket,
        lock_keys: set[str] | None = None,
        initial_message: dict[str, Any] | None = None,
    ) -> None:
        """Handle a lock websocket connection filtered by lock keys.

        Args:
            websocket: The websocket connection to serve.
            lock_keys: Optional lock keys to subscribe to.
            initial_message: Optional initial snapshot sent after connect.
        """
        await self._handle_scoped_websocket(
            websocket,
            self.lock_connection_manager,
            subscriptions=lock_keys,
            initial_message=initial_message,
        )

    async def __aenter__(self) -> Self:
        """Enter the context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context manager."""
        await self.adisconnect()


T = TypeVar("T")


class FastApiAgent(BaseAgent[T], Generic[T]):
    """An Agent that uses FastAPI as its web framework.

    This agent uses `FastApiTransport` to receive messages from HTTP
    API routes and to publish scoped websocket updates for tasks, states,
    and locks.

    Example usage:

    ```python
    from fastapi import FastAPI, WebSocket
    from rekuest_next.contrib.fastapi.agent import FastApiAgent

    app = FastAPI()
    agent = FastApiAgent()


    @app.websocket("/wstasks")
    async def task_websocket(websocket: WebSocket):
        await agent.transport.handle_task_websocket(websocket)

    @app.post("/assign")
    async def assign_action(action: dict):
        message = Assign(...)
        result = await agent.transport.asubmit(message)
        return result
    ```
    """

    name: str = Field(default="FastApiAgent", description="The name of the agent.")
    transport: FastApiTransport = Field(
        default_factory=FastApiTransport,
        description="The FastAPI transport for this agent.",
    )

    def model_post_init(self, __context: Any) -> None:
        """Wire task routing so websocket subscriptions use action keys."""
        super().model_post_init(__context)
        self.transport.task_connection_manager.routing_key_resolver = (
            self.get_task_action_key_for_message
        )

    def build_task_action_key(self, assign_message: messages.Assign) -> str:
        """Build the routing key used for task websocket subscriptions."""
        return assign_message.interface or assign_message.action or assign_message.assignation

    def get_task_action_key_for_message(self, message: messages.Message) -> str | None:
        """Resolve the task action key for an outgoing message."""
        assignation = getattr(message, "assignation", None)
        if assignation is None:
            return None
        assign_message = self.managed_assignments.get(assignation)
        if assign_message is None:
            return None
        return self.build_task_action_key(assign_message)

    async def aget_task_views(
        self,
        action_keys: list[str] | None = None,
    ) -> TaskCollectionResponse:
        """Return the current task overview filtered by action keys."""
        normalized_action_keys = set(action_keys) if action_keys else None
        tasks: dict[str, TaskView] = {}

        for assignation_id, assign_message in self.managed_assignments.items():
            action_key = self.build_task_action_key(assign_message)
            if normalized_action_keys is not None and action_key not in normalized_action_keys:
                continue

            tasks[assignation_id] = TaskView(
                assignation=assignation_id,
                action_key=action_key,
                interface=assign_message.interface,
                extension=assign_message.extension,
                user=assign_message.user,
                app=assign_message.app,
                action=assign_message.action,
                running=assignation_id in self.running_assignments,
                actor_id=self.running_assignments.get(assignation_id),
            )

        return TaskCollectionResponse(count=len(tasks), tasks=tasks)

    async def aget_state_views(
        self,
        state_keys: list[str] | None = None,
    ) -> StateCollectionResponse:
        """Return current state values and revisions filtered by state keys."""
        selected_keys = set(state_keys) if state_keys else None
        states: dict[str, StateView] = {}

        for interface, state_schema in self._collected_state_schemas.items():
            if selected_keys is not None and interface not in selected_keys:
                continue
            states[interface] = StateView(
                interface=interface,
                name=state_schema.name,
                initialized=interface in self.states,
                revision=self._state_revisions.get(interface, 0),
                value=copy.deepcopy(self._current_shrunk_states.get(interface)),
            )

        return StateCollectionResponse(
            current_session=self.current_session,
            count=len(states),
            states=states,
        )

    def get_state_schemas(self) -> dict[str, StateSchemaInput]:
        """Return all collected state schema inputs."""
        return dict(self._collected_state_schemas)

    async def aget_state_schemas(self) -> dict[str, StateSchemaInput]:
        """Return all collected state schema inputs."""
        return self.get_state_schemas()

    async def aget_lock_views(
        self,
        lock_keys: list[str] | None = None,
    ) -> dict[str, LockView]:
        """Return current lock values filtered by lock key or interface."""
        selected_keys = set(lock_keys) if lock_keys else None
        locks: dict[str, LockView] = {}

        for interface, lock in self.locks.items():
            if (
                selected_keys is not None
                and interface not in selected_keys
                and lock.lock_schema.key not in selected_keys
            ):
                continue
            locking_task = lock.locking_task
            locks[interface] = LockView(
                interface=interface,
                key=lock.lock_schema.key,
                task_id=str(locking_task) if locking_task else None,
            )

        return locks

    async def apublish_states(self, list: List[StateImplementationInput]) -> None:
        """Set up the agent states."""
        print("Publishing states is not implemented for FastApiAgent yet.")

    async def aregister_definitions(self, instance_id: str, app_context: Any) -> None:
        """Register definitions with the agent."""
        print("Registering definitions is not implemented for FastApiAgent yet.")

    async def ashelve(self, instance_id, identifier, resource_id, label=None, description=None):
        raise NotImplementedError("Shelving is not implemented for FastApiAgent yet.")

    async def alock(self, key: str, assignation: str):
        """Publish a patch to the agent.  Will forward the patch to all connected clients"""
        message = messages.LockEvent(
            key=key,
            assignation=assignation,
        )
        await self.transport.asend(message)

    async def aunlock(self, key: str):
        """Publish a patch to the agent.  Will forward the patch to all connected clients"""
        message = messages.UnlockEvent(
            key=key,
        )
        await self.transport.asend(message)

    async def apublish_envelope(self, interface: str, envelope: messages.Envelope) -> None:
        """Publish a patch to the agent.  Will forward the patch to all connected clients"""
        message = messages.StatePatchEvent(
            envelope=envelope,
        )
        await self.transport.asend(message)
