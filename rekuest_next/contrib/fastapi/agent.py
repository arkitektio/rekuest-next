"""FastAPI agent transport and websocket helpers.

The FastAPI integration exposes one websocket endpoint. Clients send an init
payload after connecting to declare which task action keys, state keys, and
lock keys they want to receive. They can additionally provide
`state_update_intervals` to control per-state batching and squashing for
frontend state updates. Outgoing agent messages are then filtered by message
type and the matching subscription set.
"""

import asyncio
import copy
import logging
from dataclasses import dataclass, field as dataclass_field
from types import TracebackType
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Generic,
    List,
    Optional,
    Self,
    TypeVar,
)
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
    WebSocketSubscriptionInit,
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
    return message.state_name


def _lock_routing_key(message: messages.FromAgentMessage) -> str | None:
    """Resolve the lock key used for lock websocket subscriptions."""
    if not isinstance(message, (messages.LockEvent, messages.UnlockEvent)):
        return None
    return message.key


@dataclass(frozen=True)
class _WebSocketSubscriptions:
    """Normalized websocket subscription filters."""

    action_keys: set[str] | None = None
    state_keys: set[str] | None = None
    lock_keys: set[str] | None = None
    state_update_intervals: dict[str, float] | None = None

    @classmethod
    def from_init(cls, payload: WebSocketSubscriptionInit) -> "_WebSocketSubscriptions":
        """Build normalized subscription sets from an init payload."""

        def _normalize(values: list[str] | None) -> set[str] | None:
            if values is None:
                return None
            normalized = {value for value in values if value}
            return normalized or None

        return cls(
            action_keys=_normalize(payload.action_keys),
            state_keys=_normalize(payload.state_keys),
            lock_keys=_normalize(payload.lock_keys),
            state_update_intervals=payload.state_update_intervals,
        )

    def get_state_update_interval(self, state_name: str) -> float:
        """Return the configured batching interval for a state key."""
        if self.state_update_intervals is None:
            return 0.0
        interval = self.state_update_intervals.get(
            state_name,
            self.state_update_intervals.get("*", 0.0),
        )
        return max(interval, 0.0)


@dataclass
class _BufferedState:
    """Buffered state patch events for one connection and state."""

    state_name: str
    patches: list[messages.StatePatchEvent] = dataclass_field(default_factory=list)


@dataclass
class _ManagedWebSocketConnection:
    """Connection state for a single websocket client."""

    subscriptions: _WebSocketSubscriptions
    pending_states: dict[str, _BufferedState] = dataclass_field(default_factory=dict)
    flush_tasks: dict[str, asyncio.Task[None]] = dataclass_field(default_factory=dict)


class FastAPIConnectionManager:
    """Manage websocket connections for multiplexed task, state, and lock updates."""

    def __init__(self) -> None:
        """Initialize empty connection and subscription registries."""
        self._active_connections: set[WebSocket] = set()
        self._connections: dict[WebSocket, _ManagedWebSocketConnection] = {}
        self._lock = asyncio.Lock()
        self.task_routing_key_resolver: Callable[[messages.FromAgentMessage], str | None] | None = (
            None
        )

    def get_task_routing_key(self, message: messages.FromAgentMessage) -> str | None:
        """Resolve the task routing key for an outgoing message."""
        if self.task_routing_key_resolver is not None:
            return self.task_routing_key_resolver(message)
        return _task_routing_key(message)

    async def connect(
        self,
        websocket: WebSocket,
        subscriptions: _WebSocketSubscriptions,
    ) -> None:
        """Register an accepted websocket with its subscriptions.

        Args:
            websocket: The websocket connection to register.
            subscriptions: The normalized subscription filters for the websocket.
        """
        async with self._lock:
            self._active_connections.add(websocket)
            self._connections[websocket] = _ManagedWebSocketConnection(subscriptions=subscriptions)
        logger.info(f"WebSocket connected. Total connections: {len(self._active_connections)}")

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a websocket connection and its subscriptions.

        Args:
            websocket: The websocket connection to remove.
        """
        flush_tasks: list[asyncio.Task[None]] = []
        async with self._lock:
            self._active_connections.discard(websocket)
            connection_state = self._connections.pop(websocket, None)
            if connection_state is not None:
                flush_tasks = list(connection_state.flush_tasks.values())
        for flush_task in flush_tasks:
            flush_task.cancel()
        logger.info(f"WebSocket disconnected. Total connections: {len(self._active_connections)}")

    async def broadcast_model(self, message: messages.FromAgentMessage) -> None:
        """Broadcast a message to websocket clients that subscribed to it.

        Args:
            message: The outgoing agent message to distribute.
        """
        if _is_state_message(message):
            await self._buffer_or_broadcast_state_message(message)
            return

        message_json = message.model_dump_json()
        async with self._lock:
            disconnected: List[WebSocket] = []
            for connection in self._active_connections:
                connection_state = self._connections.get(connection)
                if connection_state is None or not self._matches_subscription(
                    connection_state.subscriptions, message
                ):
                    continue
                try:
                    await connection.send_text(message_json)
                except Exception as e:
                    logger.warning(f"Failed to send message to WebSocket: {e}")
                    disconnected.append(connection)

        for connection in disconnected:
            await self.disconnect(connection)

    async def _buffer_or_broadcast_state_message(
        self,
        message: messages.StatePatchEvent,
    ) -> None:
        """Batch or immediately forward a state patch event per connection."""
        state_name = message.state_name
        immediate_connections: list[WebSocket] = []

        async with self._lock:
            for websocket in self._active_connections:
                connection_state = self._connections.get(websocket)
                if connection_state is None or not self._matches_subscription(
                    connection_state.subscriptions, message
                ):
                    continue

                interval = connection_state.subscriptions.get_state_update_interval(state_name)
                if interval <= 0:
                    immediate_connections.append(websocket)
                    continue

                buffered = connection_state.pending_states.get(state_name)
                if buffered is None:
                    buffered = _BufferedState(state_name=state_name)
                    connection_state.pending_states[state_name] = buffered

                buffered.patches.append(message)

                flush_task = connection_state.flush_tasks.get(state_name)
                if flush_task is None or flush_task.done():
                    connection_state.flush_tasks[state_name] = asyncio.create_task(
                        self._flush_state_buffer(websocket, state_name, interval)
                    )

        message_json = message.model_dump_json()
        for websocket in immediate_connections:
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                logger.warning(f"Failed to send message to WebSocket: {e}")
                await self.disconnect(websocket)

    async def _flush_state_buffer(
        self,
        websocket: WebSocket,
        state_name: str,
        interval: float,
    ) -> None:
        """Flush a buffered state patch batch for one websocket and state."""
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            return

        squashed_patches: list[messages.StatePatchEvent] = []
        async with self._lock:
            connection_state = self._connections.get(websocket)
            if connection_state is None:
                return

            buffered = connection_state.pending_states.pop(state_name, None)
            connection_state.flush_tasks.pop(state_name, None)
            if buffered is None:
                return

            squashed_patches = self._squash_state_patches(buffered.patches)

        for patch in squashed_patches:
            try:
                await websocket.send_text(patch.model_dump_json())
            except Exception as e:
                logger.warning(f"Failed to send message to WebSocket: {e}")
                await self.disconnect(websocket)
                break

    def _squash_state_patches(
        self,
        patches: list[messages.StatePatchEvent],
    ) -> list[messages.StatePatchEvent]:
        """Squash repeated operations on the same JSON path within one batch."""
        latest_by_path: dict[str, tuple[int, messages.StatePatchEvent]] = {}
        for index, patch in enumerate(patches):
            latest_by_path[patch.path] = (index, patch)
        return [patch for _, patch in sorted(latest_by_path.values(), key=lambda item: item[0])]

    def _matches_subscription(
        self,
        subscriptions: _WebSocketSubscriptions,
        message: messages.FromAgentMessage,
    ) -> bool:
        """Return whether a message matches a websocket subscription set."""
        if _is_state_message(message):
            state_key = _state_routing_key(message)
            return state_key is not None and (
                subscriptions.state_keys is None or state_key in subscriptions.state_keys
            )

        if _is_lock_message(message):
            lock_key = _lock_routing_key(message)
            return lock_key is not None and (
                subscriptions.lock_keys is None or lock_key in subscriptions.lock_keys
            )

        action_key = self.get_task_routing_key(message)
        return action_key is not None and (
            subscriptions.action_keys is None or action_key in subscriptions.action_keys
        )

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


class FastApiTransport(AgentTransport):
    """Transport for FastAPI-based agents.

    This transport accepts incoming command messages from HTTP routes through
    `asubmit()` and forwards outgoing agent messages through a single websocket
    manager. Each websocket connection announces the task, state, and lock keys
    it wants to receive during its init handshake.
    """

    connection_manager: FastAPIConnectionManager = Field(
        default_factory=FastAPIConnectionManager,
        description="The websocket connection manager for multiplexed updates.",
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
        """Route an outgoing agent message by message type and subscriptions.

        Task messages are matched against `action_keys`, state patch messages
        against `state_keys`, and lock lifecycle messages against `lock_keys`.
        The connection manager handles the actual per-socket filtering.

        Args:
            message: The message to send to subscribed websocket clients.
        """
        message_json = message.model_dump_json()
        logger.info(f"Agent sending message: {message_json}")
        await self.connection_manager.broadcast_model(message)

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

    async def handle_websocket(
        self,
        websocket: WebSocket,
        build_initial_payload: Callable[
            [WebSocketSubscriptionInit], Awaitable[dict[str, Any] | None]
        ]
        | None = None,
    ) -> None:
        """Serve the unified websocket endpoint.

        The websocket must send a JSON init payload immediately after connect.
        The payload may contain `action_keys`, `state_keys`, and `lock_keys`
        arrays that define which updates should be delivered. It may also
        contain `state_update_intervals`, a dictionary of per-state debounce
        intervals in seconds used for batching and squashing state updates.

        Args:
            websocket: The accepted websocket connection.
            build_initial_payload: Optional callback used to construct the first
                snapshot message after the init payload has been received.
        """
        await websocket.accept()
        try:
            init_data = await websocket.receive_json()
            if not isinstance(init_data, dict):
                raise ValueError("Websocket init payload must be a JSON object")

            init_payload = WebSocketSubscriptionInit.model_validate(init_data)
            subscriptions = _WebSocketSubscriptions.from_init(init_payload)
            await self.connection_manager.connect(websocket, subscriptions)

            if build_initial_payload is not None:
                initial_message = await build_initial_payload(init_payload)
                if initial_message is not None:
                    await websocket.send_json(initial_message)

            while True:
                await websocket.receive()
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            await self.connection_manager.disconnect(websocket)

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
    API routes and to publish multiplexed websocket updates for tasks,
    states, and locks over a single `/ws` endpoint.

    Example usage:

    ```python
    from fastapi import FastAPI, WebSocket
    from rekuest_next.contrib.fastapi.agent import FastApiAgent

    app = FastAPI()
    agent = FastApiAgent()


    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await agent.handle_websocket(websocket)

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
        self.transport.connection_manager.task_routing_key_resolver = (
            self.get_task_action_key_for_message
        )

    async def abuild_websocket_init_message(
        self,
        init_payload: WebSocketSubscriptionInit,
    ) -> dict[str, Any]:
        """Build the initial websocket snapshot for a newly connected client."""
        tasks = await self.aget_task_views(init_payload.action_keys)
        states = await self.aget_state_views(init_payload.state_keys)
        locks = await self.aget_lock_views(init_payload.lock_keys)
        return {
            "type": "INIT",
            "tasks": tasks.model_dump(mode="json"),
            "states": states.model_dump(mode="json"),
            "locks": {
                "count": len(locks),
                "locks": {key: value.model_dump(mode="json") for key, value in locks.items()},
            },
        }

    async def handle_websocket(self, websocket: WebSocket) -> None:
        """Serve the unified websocket endpoint for this agent."""
        await self.transport.handle_websocket(
            websocket,
            build_initial_payload=self.abuild_websocket_init_message,
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
                value=copy.deepcopy(self._current_shrunk_states.get(interface)),
            )

        return StateCollectionResponse(
            current_session=self.current_session,
            current_global_revision=self.global_revision,
            count=len(states),
            states=states,
        )

    async def aget_checkout_state_views(
        self,
        global_revision_id: int,
        state_keys: list[str] | None = None,
        session_id: str | None = None,
    ) -> StateCollectionResponse:
        """Return reconstructed state values for a historical global revision."""
        selected_keys = set(state_keys) if state_keys else None
        resolved_session_id = session_id or self.current_session
        states: dict[str, StateView] = {}

        for interface, state_schema in self._collected_state_schemas.items():
            if selected_keys is not None and interface not in selected_keys:
                continue

            snapshot = await self.retriever.aget_state_at_global_rev(
                global_revision_id,
                state_id=interface,
                session_id=resolved_session_id,
            )

            if snapshot is None or isinstance(snapshot, list):
                states[interface] = StateView(
                    interface=interface,
                    name=state_schema.name,
                    initialized=False,
                    value=None,
                )
                continue

            states[interface] = StateView(
                interface=interface,
                name=state_schema.name,
                initialized=True,
                value=copy.deepcopy(snapshot.data),
            )

        return StateCollectionResponse(
            current_session=resolved_session_id,
            current_global_revision=global_revision_id,
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

    async def apublish_patch(self, patch: messages.StatePatchEvent) -> None:
        """Publish a state patch event to all connected websocket clients."""
        await self.transport.asend(patch)
