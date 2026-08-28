"""WebSocket transport used by agents to exchange messages with the backend."""

import time
import warnings
from types import TracebackType
from typing import Awaitable, Callable, Dict, List, Optional, Self, Type, cast
import pydantic
import websockets
from rekuest_next.agents.policy import Backoff, ConnectionPolicy
from rekuest_next.agents.transport.base import AgentTransport
from rekuest_next.agents.transport.types import HandshakeParams
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


# Close codes the backend uses (``facade/codes.py`` on the server). The 3xxx codes
# are protocol faults the backend attributes to *this* client; the 4xxx codes are
# policy decisions about the agent.
HEARTBEAT_NOT_RESPONDED_CODE = 3001
INVALID_JSON_CODE = 3002
SCHEMA_MISMATCH_CODE = 3003
BEFORE_REGISTRATION_CODE = 3004
BLOCKED_CODE = 4003
BUSY_CODE = 4004
"""Rejected: another connection is live for this agent and ``force`` was not set."""
KICK_CODE = 4005
"""Displaced: a newer connection registered for this agent with ``force``."""
BOUNCED_CODE = BEFORE_REGISTRATION_CODE


agent_error_codes: Dict[int, Type[Exception]] = {
    KICK_CODE: AgentWasKicked,
    BUSY_CODE: AgentIsAlreadyBusy,
    BLOCKED_CODE: AgentWasBlocked,
    # We sent something the backend could not parse. Reconnecting would only
    # resend it, so this is a definite failure, not a retry.
    INVALID_JSON_CODE: DefiniteConnectionFail,
    SCHEMA_MISMATCH_CODE: DefiniteConnectionFail,
}

agent_error_message: Dict[int, str] = {
    KICK_CODE: "Agent was kicked by the server",
    BUSY_CODE: "Agent can't connect as another instance is already connected. Please kick the other instance first",
    BLOCKED_CODE: "Agent is currently blocked by the server. Unblock first!",
    INVALID_JSON_CODE: "The backend rejected a message from this agent as invalid JSON",
    SCHEMA_MISMATCH_CODE: "The backend rejected a message from this agent as not matching its schema",
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
    max_retries: Optional[int] = None
    """Deprecated. Set ``ConnectionPolicy.max_retries`` on the agent instead."""
    time_between_retries: Optional[float] = None
    """Deprecated. Set ``ConnectionPolicy.backoff`` on the agent instead. When given it
    pins a flat (non-exponential) delay, reproducing the old behaviour exactly."""
    allow_reconnect: Optional[bool] = None
    """Deprecated. ``False`` is equivalent to ``ConnectionPolicy(max_retries=0)``."""
    auto_connect: bool = True
    force: bool = False
    """If another connection is already registered for this agent, kick it and take over."""
    flush_timeout: float = 5.0
    """Maximum seconds to spend sending still-queued messages when disconnecting. Bounds
    the flush so a dead socket cannot hang teardown."""

    _healthy: ContextBool = False
    _closing: ContextBool = False
    _drop_times: List[float] = pydantic.PrivateAttr(default_factory=list)

    @pydantic.model_validator(mode="after")
    def _warn_on_deprecated_retry_knobs(self) -> "WebsocketAgentTransport":
        """Nudge callers towards the agent-level policy without breaking them."""
        if (
            self.max_retries is not None
            or self.time_between_retries is not None
            or self.allow_reconnect is not None
        ):
            warnings.warn(
                "max_retries/time_between_retries/allow_reconnect on "
                "WebsocketAgentTransport are deprecated; set ConnectionPolicy on the "
                "agent instead. They still work, and override the agent's policy.",
                DeprecationWarning,
                stacklevel=2,
            )
        return self

    @property
    def connection_policy(self) -> ConnectionPolicy:
        """The agent's policy, with any deprecated per-transport knob layered on top.

        The knobs win where they are set: someone who explicitly built a transport
        with ``time_between_retries=0`` means it, and should not have it quietly
        replaced by the agent's default backoff.
        """
        policy = super().connection_policy
        overrides: Dict[str, object] = {}
        if self.max_retries is not None:
            overrides["max_retries"] = self.max_retries
        if self.time_between_retries is not None:
            overrides["backoff"] = Backoff(
                initial=self.time_between_retries,
                factor=1.0,
                max=self.time_between_retries,
                jitter=0.0,
            )
        if self.allow_reconnect is False:
            overrides["max_retries"] = 0
        return policy.model_copy(update=overrides) if overrides else policy

    def _is_flapping(self, policy: ConnectionPolicy) -> bool:
        """Whether the link has dropped too often lately to be worth chasing.

        The backstop for the case ``reset_after`` cannot see: a link that stays up
        just long enough to refund the retry budget on every cycle would otherwise
        reconnect forever.
        """
        if policy.flap_limit is None:
            return False
        cutoff = time.monotonic() - policy.flap_window
        self._drop_times = [t for t in self._drop_times if t >= cutoff]
        return len(self._drop_times) >= policy.flap_limit

    @property
    def connected(self) -> bool:
        """Whether a socket is live right now (set while the receive loop is running)."""
        return bool(self._healthy)

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
        self._send_queue = asyncio.Queue()
        self._in_queue = asyncio.Queue()
        self._closing = False
        self._client = None
        # Per-session, like everything above it: drops from a previous session must
        # not count towards this one's flap budget.
        self._drop_times.clear()
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
            # A previous connection task in this session ended by pushing its
            # ``CLOSED`` sentinel (or terminal failure). Nothing from that session
            # may be seen by the receiver of this one, or ``areceive`` ends before
            # the new socket has even opened.
            while not self._in_queue.empty():
                self._in_queue.get_nowait()
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

    async def _aget_handshake(self) -> HandshakeParams:
        """Resolve the handshake for one connect attempt.

        The agent's host is what makes the ``session_id`` identifying this process
        reach ``Register`` at all. With no host installed the transport still works
        on its own (as the transport tests use it), registering with its build-time
        ``force`` policy and no session id.
        """
        if self._host is None:
            return HandshakeParams(force=self.force)
        params = await self._host.aget_handshake_params()
        # "No opinion" from the agent leaves the build-time policy in place.
        if params.force is None:
            params = params.model_copy(update={"force": self.force})
        return params

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

    async def _ahandle_inbound(self, message: str) -> None:
        """Dispatch one raw frame from the socket.

        Heartbeats are answered on the spot; ``Bounce``/``Kick`` are raised so the
        receive loop's ``except`` arms classify them; everything else is handed to the
        agent through the inbound queue. Frames that fail to parse are logged and
        dropped, never fatal.
        """
        assert self._in_queue is not None, "Should be entered"
        try:
            payload = InMessagePayload(message=json.loads(message))
        except pydantic.ValidationError:
            logger.error(f"Received non-json message: {message}", exc_info=True)
            return
        logger.debug(f"<<<< {payload}")

        if isinstance(payload.message, messages.Heartbeat):
            await self.asend(messages.HeartbeatEvent())
        elif isinstance(payload.message, messages.Bounce):
            raise BounceError("Was bounced. Debug call to reconnect")
        elif isinstance(payload.message, messages.Kick):
            raise KickError(
                f"Agent was kicked by the server: {payload.message.reason or 'No reason provided'}"
            )
        else:
            self._in_queue.put_nowait(payload.message)

    @staticmethod
    def _classify_close(e: ConnectionClosedError) -> Exception:
        """Turn a closed connection into the failure the retry loop should see.

        Known agent error codes map to their dedicated exceptions; a bounce and
        every other close are correctable (the loop reconnects).
        """
        # The close code the peer sent, or ABNORMAL_CLOSURE when it never sent a
        # close frame.
        close_code = e.rcvd.code if e.rcvd is not None else CloseCode.ABNORMAL_CLOSURE

        if close_code in agent_error_codes:
            return agent_error_codes[close_code](agent_error_message[close_code])
        if close_code == BOUNCED_CODE:
            return CorrectableConnectionFail("Was bounced. Debug call to reconnect")
        return CorrectableConnectionFail(
            "Connection failed unexpectably. Reconnectable."
        )

    async def _aconnect_and_receive(self) -> None:
        """The connect/register/receive/retry loop itself."""
        assert self._in_queue is not None, "Should be entered"
        retry = 0

        while True:
            if self._closing:
                # Disconnect was requested; stop the (re)connect loop cleanly.
                return
            send_task = None
            connected_at: Optional[float] = None
            try:
                try:
                    # The credential is the transport's to load, and is reloaded per
                    # attempt so a reconnect never presents a stale token.
                    token = await self.token_loader()
                    handshake = await self._aget_handshake()
                    async with websockets.connect(
                        f"{self.endpoint_url}",
                        ssl=(
                            self.ssl_context
                            if self.endpoint_url.startswith("wss")
                            else None
                        ),
                    ) as client:
                        connected_at = time.monotonic()
                        self._client = client
                        logger.info("Agent on Websockets connected")

                        await client.send(
                            messages.Register(
                                token=token,
                                force=bool(handshake.force),
                                session_id=handshake.session_id,
                            ).model_dump_json()
                        )

                        send_task = asyncio.create_task(self.sending(client))
                        self._healthy = True
                        await self.anotify_connection_change(True)

                        async for message in client:
                            assert isinstance(message, str), (
                                "Message should be a string"
                            )
                            await self._ahandle_inbound(message)

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
                    raise self._classify_close(e) from e

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
                    was_healthy = bool(self._healthy)
                    self._healthy = False
                    if was_healthy:
                        self._drop_times.append(time.monotonic())
                    # The budget is refunded only by a connection that stood up long
                    # enough to count as a recovery. Refunding it on every successful
                    # connect (as this used to) makes ``max_retries`` meaningless
                    # against a link that connects and immediately drops.
                    if (
                        connected_at is not None
                        and (time.monotonic() - connected_at)
                        >= self.connection_policy.reset_after
                    ):
                        retry = 0

            except CorrectableConnectionFail as e:
                if self._closing:
                    # Disconnect was requested while connected; do not reconnect.
                    return
                logger.info(f"Trying to Recover from Exception {e}")
                # The agent could not see this window before: the drop is real, but
                # ``areceive()`` will not end because we are about to retry.
                await self.anotify_connection_change(False)

                policy = self.connection_policy
                if retry >= policy.max_retries:
                    logger.error("Max retries reached. Giving up")
                    raise DefiniteConnectionFail("Exceeded Number of Retries")
                if self._is_flapping(policy):
                    logger.error("Connection is flapping. Giving up")
                    raise DefiniteConnectionFail(
                        f"Connection dropped {len(self._drop_times)} times within "
                        f"{policy.flap_window}s"
                    )

                delay = policy.backoff.delay_for(retry)
                logger.info(f"Waiting for some time before retrying: {delay}")
                await asyncio.sleep(delay)
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
        # The message currently taken off the queue but not yet acknowledged. If this
        # task dies holding one — either because the send failed or because the
        # receive loop noticed the drop first and cancelled us mid-send — that
        # message has to go back, or it is simply lost. Only terminal reports are
        # retained elsewhere; a Progress, Log or Yield popped here would vanish.
        in_flight: Optional[str] = None

        def requeue() -> None:
            """Put the held message back, then close out the get that took it.

            Order matters: putting first keeps the queue's unfinished count above
            zero throughout, so a concurrent ``aflush`` join() can never observe a
            transiently drained queue and return early.
            """
            nonlocal in_flight
            if in_flight is None:
                return
            assert self._send_queue is not None
            self._send_queue.put_nowait(in_flight)
            self._send_queue.task_done()
            in_flight = None

        try:
            while True:
                in_flight = await self._send_queue.get()
                try:
                    await client.send(in_flight)
                except Exception:  # noqa: BLE001 — the socket died under us
                    # Return cleanly rather than letting this propagate. The connect
                    # loop's ``finally`` awaits this task, so an exception stored
                    # here would surface there, replace the in-flight
                    # CorrectableConnectionFail, escape the retry handler, and turn a
                    # recoverable drop into a full agent teardown.
                    requeue()
                    logger.info(
                        "Send failed; message requeued for the next connection",
                        exc_info=True,
                    )
                    return
                self._send_queue.task_done()
                in_flight = None
        except asyncio.CancelledError:
            # The usual path for a dropped socket: the receive loop sees the close
            # first and cancels this task while it is still inside client.send().
            requeue()
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
