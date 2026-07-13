"""WebSocket transport used by agents to exchange messages with the backend."""

from types import TracebackType
from typing import Awaitable, Callable, Dict, Optional, Self, Type, cast
import pydantic
import websockets
from rekuest_next.agents.transport.base import AgentTransport
import asyncio
import json
from rekuest_next.agents.transport.errors import (
    AgentTransportException,
)
from rekuest_next import messages
import logging
from websockets.exceptions import (
    ConnectionClosedError,
    InvalidHandshake,
)
from websockets.frames import CloseCode
from pydantic import ConfigDict, Field
import ssl
import certifi
from koil.types import ContextBool, Contextual
from .errors import (
    BounceError,
    CorrectableConnectionFail,
    DefiniteConnectionFail,
    AgentWasKicked,
    AgentIsAlreadyBusy,
    AgentWasBlocked,
    KickError,
)
from typing import AsyncIterator

from pydantic import BaseModel


class InMessagePayload(BaseModel):
    """Typed wrapper for a single backend payload received over the socket."""

    message: messages.ToAgentMessage = Field(
        discriminator="type",
    )


logger = logging.getLogger(__name__)


async def token_loader() -> str:
    """Placeholder token loader used until a real authentication callback is set."""
    raise NotImplementedError(
        "Websocket transport does need a defined token_loader on Connection"
    )


KICK_CODE = 3001
BUSY_CODE = 3002
BLOCKED_CODE = 4003
BOUNCED_CODE = 3004


agent_error_codes: Dict[int, Type[Exception]] = {
    KICK_CODE: AgentWasKicked,
    BUSY_CODE: AgentIsAlreadyBusy,
    BLOCKED_CODE: AgentWasBlocked,
}

agent_error_message: Dict[int, str] = {
    KICK_CODE: "Agent was kicked by the server",
    BUSY_CODE: "Agent can't connect as another instance is already connected. Please kick the other instance first",
    BLOCKED_CODE: "Agent is currently blocked by the server. Unblock first!",
}


class _Closed:
    """Sentinel pushed onto the inbound queue when the connection loop is done."""


CLOSED = _Closed()


class WebsocketAgentTransport(AgentTransport):
    """Reconnect-capable transport for the agent WebSocket protocol.

    Typical usage is:

    1. instantiate the transport with an endpoint URL and ``token_loader``
    2. enter it as an async context manager to initialize local state
    3. call ``aconnect()`` to open the socket and register the agent
    4. consume ``areceive()`` for backend messages, ``asend(...)`` to queue outbound ones
    5. call ``adisconnect()`` to flush and close

    The socket is owned by a background connection task started in ``aconnect()``,
    not by the ``areceive()`` iterator. That is what lets an agent keep publishing
    while it tears down: cancelling the consumer of ``areceive()`` (the agent loop)
    leaves the connection up, so messages produced during teardown still reach the
    backend, and the socket is closed only by ``adisconnect()``.

    The connection task opens the socket, registers the agent instance, replies to
    heartbeats, retries recoverable failures, and hands received messages (and any
    terminal failure) to ``areceive()`` through an inbound queue.
    """

    endpoint_url: str
    ssl_context: ssl.SSLContext = Field(
        default_factory=lambda: ssl.create_default_context(cafile=certifi.where())
    )
    token_loader: Callable[[], Awaitable[str]] = Field(exclude=True)
    max_retries: int = 5
    time_between_retries: float = 3
    allow_reconnect: bool = True
    auto_connect: bool = True
    force: bool = False
    """If another connection is already registered for this agent, kick it and take over."""
    mode: messages.AgentMode = messages.AgentMode.EXECUTOR
    """How this participant intends to use the protocol. ``EXECUTOR`` is enough for
    actor-internal (dependent) calls; set ``ORCHESTRATOR`` to also originate root tasks from
    the agent. The mode is only granted if the token carries the matching capability scopes."""
    flush_timeout: float = 5.0
    """Maximum seconds to spend sending still-queued messages when disconnecting. Bounds
    the flush so a dead socket cannot hang teardown."""

    _futures: Contextual[Dict[str, asyncio.Future[str]]] = None
    _healthy: ContextBool = False
    _closing: ContextBool = False
    _send_queue: Contextual[asyncio.Queue[str]] = None
    _in_queue: Contextual[asyncio.Queue[object]] = None
    _connection_task: Contextual[asyncio.Task[None]] = None
    _client: Contextual["websockets.ClientConnection"] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def __aenter__(self) -> Self:
        """Initialize per-session state used by the transport context.

        This prepares the inbound and outbound queues and the pending-future
        registry. The network connection is opened by ``aconnect()``.
        """
        self._futures = {}
        self._send_queue = asyncio.Queue()
        self._in_queue = asyncio.Queue()
        self._closing = False
        self._client = None
        return self

    async def aconnect(self) -> None:
        """Start the connection task that owns the WebSocket.

        The task opens the socket and registers the agent; the backend binds the
        agent to its instance based on the authentication token. Received messages
        are handed to ``areceive()`` through the inbound queue.
        """
        if self._in_queue is None or self._send_queue is None:
            raise AgentTransportException(
                "Transport was not entered. Use it as an async context manager."
            )

        self._closing = False
        if self._connection_task is None or self._connection_task.done():
            self._connection_task = asyncio.create_task(self._aconnection_loop())

    async def areceive(self) -> AsyncIterator[messages.ToAgentMessage]:
        """Yield the backend messages the connection task has received.

        Ends when the connection is closed, and raises whatever terminal failure
        the connection task hit (``DefiniteConnectionFail``, ``AgentWasKicked``, …)
        as if the socket were being read here.
        """
        if self._in_queue is None:
            raise AgentTransportException(
                "Transport was not entered. Use it as an async context manager."
            )

        while True:
            item = await self._in_queue.get()
            if isinstance(item, _Closed):
                return
            if isinstance(item, BaseException):
                raise item
            yield cast(messages.ToAgentMessage, item)

    async def _aconnection_loop(self) -> None:
        """Own the socket: connect, register, receive, retry — until disconnected.

        Terminal failures are handed to the ``areceive()`` consumer instead of
        being raised here, since nobody awaits this task.
        """
        assert self._in_queue is not None, "Should be entered"
        try:
            await self._aconnect_and_receive()
        except asyncio.CancelledError:
            raise
        except BaseException as e:  # noqa: BLE001 — forwarded to the consumer
            self._in_queue.put_nowait(e)
        finally:
            # put_nowait so this still runs when the task is being cancelled.
            self._in_queue.put_nowait(CLOSED)

    async def _aconnect_and_receive(self) -> None:
        """The connect/register/receive/retry loop itself."""
        assert self._in_queue is not None, "Should be entered"
        retry = 0

        while True:
            if self._closing:
                # Disconnect was requested; stop the (re)connect loop cleanly.
                return
            send_task = None
            try:
                try:
                    token = await self.token_loader()
                    async with websockets.connect(
                        f"{self.endpoint_url}",
                        ssl=(
                            self.ssl_context
                            if self.endpoint_url.startswith("wss")
                            else None
                        ),
                    ) as client:
                        retry = 0
                        self._client = client
                        logger.info("Agent on Websockets connected")

                        await client.send(
                            messages.Register(
                                token=token,
                                force=self.force,
                                mode=self.mode,
                            ).model_dump_json()
                        )

                        send_task = asyncio.create_task(self.sending(client))
                        self._healthy = True

                        async for message in client:
                            assert isinstance(message, str), (
                                "Message should be a string"
                            )
                            try:
                                payload = InMessagePayload(message=json.loads(message))
                                logger.debug(f"<<<< {payload}")

                                if isinstance(payload.message, messages.Heartbeat):
                                    await self.asend(messages.HeartbeatEvent())
                                elif isinstance(payload.message, messages.Bounce):
                                    raise BounceError(
                                        "Was bounced. Debug call to reconnect"
                                    )
                                elif isinstance(payload.message, messages.Kick):
                                    raise KickError(
                                        f"Agent was kicked by the server: {payload.message.reason or 'No reason provided'}"
                                    )
                                else:
                                    self._in_queue.put_nowait(payload.message)
                            except pydantic.ValidationError:
                                logger.error(
                                    f"Received non-json message: {message}",
                                    exc_info=True,
                                )

                except InvalidHandshake as e:
                    logger.warning(
                        (
                            "Websocket to"
                            f" {self.endpoint_url}?token=******* was"
                            " denied. Trying to reload token"
                        ),
                        exc_info=True,
                    )
                    raise CorrectableConnectionFail(
                        "Received an InvalidHandshake"
                    ) from e

                except BounceError as e:
                    logger.warning("Received Bounce message", exc_info=True)
                    raise CorrectableConnectionFail(
                        "Was bounced. Debug call to reconnect"
                    ) from e

                except KickError as e:
                    logger.warning("Agent was kicked by the server", exc_info=True)
                    raise DefiniteConnectionFail("Agent was kicked") from e

                except ConnectionClosedError as e:
                    logger.warning("Websocket was closed", exc_info=True)

                    # The close code the peer sent, or ABNORMAL_CLOSURE when it
                    # never sent a close frame.
                    close_code = (
                        e.rcvd.code
                        if e.rcvd is not None
                        else CloseCode.ABNORMAL_CLOSURE
                    )

                    if close_code in agent_error_codes:
                        raise agent_error_codes[close_code](
                            agent_error_message[close_code]
                        )

                    if close_code == BOUNCED_CODE:
                        raise CorrectableConnectionFail(
                            "Was bounced. Debug call to reconnect"
                        ) from e
                    else:
                        raise CorrectableConnectionFail(
                            "Connection failed unexpectably. Reconnectable."
                        ) from e

                except Exception as e:
                    logger.error("Websocket excepted closed definetely", exc_info=True)
                    logger.critical("Unhandled exception... ", exc_info=True)
                    raise DefiniteConnectionFail(e) from e

                finally:
                    self._client = None
                    if send_task:
                        send_task.cancel()
                        try:
                            await send_task
                        except asyncio.CancelledError:
                            pass
                    self._healthy = False

            except CorrectableConnectionFail as e:
                if self._closing:
                    # Disconnect was requested while connected; do not reconnect.
                    return
                logger.info(f"Trying to Recover from Exception {e}")
                if retry > self.max_retries or not self.allow_reconnect:
                    logger.error("Max retries reached. Giving up")
                    raise DefiniteConnectionFail("Exceeded Number of Retries")

                logger.info(
                    f"Waiting for some time before retrying: {self.time_between_retries}"
                )
                await asyncio.sleep(self.time_between_retries)
                logger.info("Retrying to connect")
                retry += 1
                continue

            except asyncio.CancelledError as e:
                logger.info("Websocket got cancelled. Trying to shutdown graceully")
                raise e

    async def sending(self, client: websockets.ClientConnection) -> None:
        """Drain queued outbound messages into the active WebSocket connection."""
        if not self._send_queue:
            raise AgentTransportException(
                "No send queue set. Can't send messages to the agent transport"
            )
        try:
            while True:
                message = await self._send_queue.get()
                await client.send(message)
                self._send_queue.task_done()
        except asyncio.CancelledError:
            logger.info("Sending Task sucessfully Cancelled")

    async def delayaction(self, action: messages.FromAgentMessage) -> None:
        """Serialize and enqueue an outbound message for the sender task.

        Messages are queued even when the caller is not writing directly to the
        socket; the background sender started by ``areceive()`` flushes them in
        order.
        """
        assert self._send_queue, "Should be connected"
        logger.debug(">>>>> Sending message %s", action.model_dump_json())
        await self._send_queue.put(action.model_dump_json())

    async def asend(self, message: messages.FromAgentMessage) -> None:
        """Public send API used by the agent runtime to queue one message."""
        await self.delayaction(message)

    async def aflush(self) -> None:
        """Wait for the sender task to put everything still queued on the wire.

        Messages produced during teardown (a shutdown hook's state patch, an
        actor's last write) are queued while the socket is closing, so without
        this the close can outrun the sender task and drop them. Waiting on the
        queue rather than sending here keeps ``client.send`` single-writer.
        """
        if self._client is None or self._send_queue is None:
            # The receive loop owns the socket and cancels the sender task with
            # it, so with no client there is nobody left to drain the queue.
            return

        await self._send_queue.join()

    async def adisconnect(self) -> None:
        """Explicit disconnect: flush, stop reconnecting, and close the socket.

        This is the only thing that closes the connection. Everything still queued
        is put on the wire first (bounded by ``flush_timeout``), so messages an
        agent produces while tearing down are not lost. Setting ``_closing`` makes
        the connection task exit instead of retrying, and closing the live client
        unblocks a receive that is otherwise stuck, so teardown can complete and
        the server releases the agent registration promptly.
        """
        self._closing = True
        client = self._client
        if client is not None:
            try:
                await asyncio.wait_for(self.aflush(), timeout=self.flush_timeout)
            except Exception:
                logger.warning(
                    "Failed to flush queued agent messages before disconnecting",
                    exc_info=True,
                )
            try:
                await client.close()
            except Exception:
                logger.warning("Failed to close agent websocket", exc_info=True)

        task = self._connection_task
        if task is not None:
            # Closing the client makes the loop fall out on its own; only cancel if
            # it ignores that, so a clean shutdown stays clean.
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=self.flush_timeout)
            except asyncio.TimeoutError:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.warning("Agent connection task failed", exc_info=True)
            self._connection_task = None

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        """Exit the transport context, closing the connection if it is still up."""
        if self._connection_task is not None or self._client is not None:
            await self.adisconnect()
