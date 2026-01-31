"""FastAPI Agent module for rekuest_next.

This module provides a FastAPI-based agent transport that allows
messages to be sent to the agent via HTTP API routes and WebSocket
connections.
"""

from types import TracebackType
from typing import AsyncIterator, List, Optional, Self, Set, Any
import asyncio
import logging
import jsonpatch
from pydantic import ConfigDict, Field, PrivateAttr
from fastapi import WebSocket, WebSocketDisconnect

from rekuest_next.agents.base import BaseAgent
from rekuest_next.agents.transport.base import AgentTransport
from rekuest_next import messages
from rekuest_next.api.schema import StateImplementationInput


logger = logging.getLogger(__name__)


class FastAPIConnectionManager:
    """Manages WebSocket connections for FastAPI agents.

    This class tracks active WebSocket connections and allows broadcasting
    messages to all connected clients.
    """

    def __init__(self) -> None:
        """Initialize the connection manager."""
        self._active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection.

        Args:
            websocket: The WebSocket connection to register.
        """
        await websocket.accept()
        async with self._lock:
            self._active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self._active_connections)}")

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the manager.

        Args:
            websocket: The WebSocket connection to remove.
        """
        async with self._lock:
            self._active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self._active_connections)}")

    async def broadcast(self, message: str) -> None:
        """Send a message to all connected WebSocket clients.

        Args:
            message: The JSON string message to broadcast.
        """
        logger.info(f"Broadcasting to {len(self._active_connections)} clients: {message}")
        async with self._lock:
            disconnected: List[WebSocket] = []
            for connection in self._active_connections:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.warning(f"Failed to send message to WebSocket: {e}")
                    disconnected.append(connection)

            # Clean up disconnected clients
            for conn in disconnected:
                self._active_connections.discard(conn)

    async def send_personal(self, websocket: WebSocket, message: str) -> None:
        """Send a message to a specific WebSocket client.

        Args:
            websocket: The target WebSocket connection.
            message: The JSON string message to send.
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

    This transport allows the agent to receive messages from HTTP API routes
    and send responses back via WebSocket connections.

    Messages can be submitted to the agent via the `asubmit` method (called
    from API routes) and the agent will process them. Responses and events
    are broadcast to all connected WebSocket clients.
    """

    connection_manager: FastAPIConnectionManager = Field(
        default_factory=FastAPIConnectionManager,
        description="The WebSocket connection manager for broadcasting messages.",
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
        print(f"Submitted message to agent: {message}")
        logger.info(f"Submitted message to agent: {message}")

        # Return the assignation ID for tracking
        if isinstance(message, messages.Assign):
            return message.assignation
        return getattr(message, "assignation", getattr(message, "id", "unknown"))

    async def asend(self, message: messages.FromAgentMessage) -> None:
        """Send a message from the agent to connected clients.

        This broadcasts the message to all connected WebSocket clients.

        Args:
            message: The message to send.
        """
        message_json = message.model_dump_json()
        logger.info(f"Agent sending message: {message_json}")
        print(f"Agent sending message: {message_json}")

        # Broadcast to all WebSocket clients
        await self.connection_manager.broadcast(message_json)

    async def aconnect(self, instance_id: str) -> None:
        """Connect the transport.

        Args:
            instance_id: The instance ID for this agent.
        """
        self._instance_id = instance_id
        self._receive_queue = asyncio.Queue()
        self._connected = True
        print(f"FastAPI transport connected with instance_id: {instance_id}")
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
                print(f"Agent received message: {message}")
                yield message
            except asyncio.CancelledError:
                logger.info("Receive loop cancelled")
                raise

    async def adisconnect(self) -> None:
        """Disconnect the transport."""
        self._connected = False
        self._receive_queue = None
        logger.info("FastAPI transport disconnected")

    async def handle_websocket(self, websocket: WebSocket) -> None:
        """Handle a WebSocket connection.

        This method should be called from a FastAPI WebSocket route.
        The WebSocket is used to send FromAgentMessage updates to the client.
        Clients connect and receive real-time updates (progress, done, error, etc.).

        All commands (assign, cancel, pause, resume) should be sent via API routes.

        Args:
            websocket: The WebSocket connection to handle.
        """
        await self.connection_manager.connect(websocket)
        try:
            # Keep the connection open - client just listens for broadcasts
            while True:
                # Use receive to keep connection alive and detect disconnects
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


class FastApiAgent(BaseAgent):
    """An Agent that uses FastAPI as its web framework.

    This agent uses the FastApiTransport to receive messages from HTTP
    API routes and WebSocket connections, making it suitable for building
    REST APIs that can trigger agent actions.

    Example usage:

    ```python
    from fastapi import FastAPI, WebSocket
    from rekuest_next.contrib.fastapi.agent import FastApiAgent

    app = FastAPI()
    agent = FastApiAgent()


    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await agent.transport.handle_websocket(websocket)

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

    async def apublish_states(self, list: List[StateImplementationInput]) -> None:
        """Set up the agent states."""
        print("Publishing states is not implemented for FastApiAgent yet.")

    async def aregister_definitions(self, instance_id: str, app_context: Any) -> None:
        """Register definitions with the agent."""
        print("Registering definitions is not implemented for FastApiAgent yet.")

    async def ashelve(self, instance_id, identifier, resource_id, label=None, description=None):
        return identifier

    async def alock(self, key, assignation):
        """Publish a patch to the agent.  Will forward the patch to all connected clients"""
        message = messages.LockEvent(
            key=key,
            assignation=assignation,
        )
        await self.transport.asend(message)

    async def aunlock(self, key):
        """Publish a patch to the agent.  Will forward the patch to all connected clients"""
        message = messages.UnlockEvent(
            key=key,
        )
        await self.transport.asend(message)

    async def apublish_patch(self, interface, patch: jsonpatch.JsonPatch) -> None:
        """Publish a patch to the agent.  Will forward the patch to all connected clients"""
        message = messages.StatePatchEvent(
            interface=interface,
            patch=patch.to_string(),
        )
        await self.transport.asend(message)
