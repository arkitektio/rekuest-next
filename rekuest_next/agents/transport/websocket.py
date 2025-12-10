"""Websocket Agent Transport"""

from types import TracebackType
from typing import Awaitable, Callable, Dict, Optional, Self, Type
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
from pydantic import ConfigDict, Field
import ssl
import certifi
from koil.types import ContextBool, Contextual
from .errors import (
    AgentConnectionFail,
    BounceError,
    CorrectableConnectionFail,
    DefiniteConnectionFail,
    AgentWasKicked,
    AgentIsAlreadyBusy,
    AgentWasBlocked,
    KickError,
)
from pydantic import BaseModel


class InMessagePayload(BaseModel):
    """InMessagePayload class to handle incoming messages"""

    message: messages.ToAgentMessage = Field(
        discriminator="type",
    )


logger = logging.getLogger(__name__)


async def token_loader() -> str:
    """Dummy token loader function"""
    raise NotImplementedError("Websocket transport does need a defined token_loader on Connection")


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
    BUSY_CODE: "Agent can't connect on this instance_id as another instance is already connected. Please kick the other instance first or use another instance_id",
    BLOCKED_CODE: "Agent is currently blocked by the server. Unblock first!",
}


from typing import AsyncIterator


class WebsocketAgentTransport(AgentTransport):
    """Websocket Agent Transport"""

    endpoint_url: str
    ssl_context: ssl.SSLContext = Field(
        default_factory=lambda: ssl.create_default_context(cafile=certifi.where())
    )
    token_loader: Callable[[], Awaitable[str]] = Field(exclude=True)
    max_retries: int = 5
    time_between_retries: float = 3
    allow_reconnect: bool = True
    auto_connect: bool = True

    _futures: Contextual[Dict[str, asyncio.Future[str]]] = None
    _connected: ContextBool = False
    _healthy: ContextBool = False
    _send_queue: Contextual[asyncio.Queue[str]] = None
    _connection_task: Contextual[asyncio.Task[None]] = None
    _connected_future: Contextual[asyncio.Future[bool]] = None
    _instance_id: Contextual[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def __aenter__(self) -> Self:
        """Connect to the agent transport. Sets the callback and"""
        self._futures = {}
        self._send_queue = asyncio.Queue()
        return self

    async def aconnect(self, instance_id: str) -> None:
        """Connect to the agent transport"""
        self._instance_id = instance_id

    async def areceive(self) -> AsyncIterator[messages.ToAgentMessage]:
        """Connect to the agent transport"""
        retry = 0
        reload_token = False
        instance_id = self._instance_id

        while True:
            send_task = None
            try:
                try:
                    token = await self.token_loader()
                    async with websockets.connect(
                        f"{self.endpoint_url}",
                        ssl=(self.ssl_context if self.endpoint_url.startswith("wss") else None),
                    ) as client:
                        retry = 0
                        logger.info("Agent on Websockets connected")

                        await client.send(
                            messages.Register(
                                token=token,
                                instance_id=instance_id,
                            ).model_dump_json()
                        )

                        send_task = asyncio.create_task(self.sending(client))
                        self._healthy = True

                        async for message in client:
                            assert isinstance(message, str), "Message should be a string"
                            payload = InMessagePayload(message=json.loads(message))
                            logger.debug(f"<<<< {payload}")

                            if isinstance(payload.message, messages.Heartbeat):
                                await self.asend(messages.HeartbeatEvent())
                            elif isinstance(payload.message, messages.Bounce):
                                print("Received Bounce message")
                                raise BounceError("Was bounced. Debug call to reconnect")
                            elif isinstance(payload.message, messages.Kick):
                                raise KickError(
                                    f"Agent was kicked by the server: {payload.message.reason or 'No reason provided'}"
                                )
                            else:
                                yield payload.message

                except InvalidHandshake as e:
                    print("Invalid Handshake received")
                    logger.warning(
                        (
                            "Websocket to"
                            f" {self.endpoint_url}?token=*******&instance_id={instance_id} was"
                            " denied. Trying to reload token"
                        ),
                        exc_info=True,
                    )
                    reload_token = True
                    raise CorrectableConnectionFail("Received an InvalidHandshake") from e

                except BounceError as e:
                    logger.warning("Received Bounce message", exc_info=True)
                    raise CorrectableConnectionFail("Was bounced. Debug call to reconnect") from e

                except KickError as e:
                    logger.warning("Agent was kicked by the server", exc_info=True)
                    raise DefiniteConnectionFail("Agent was kicked") from e

                except ConnectionClosedError as e:
                    logger.warning("Websocket was closed", exc_info=True)

                    if e.code in agent_error_codes:
                        raise agent_error_codes[e.code](agent_error_message[e.code])

                    if e.code == BOUNCED_CODE:
                        raise CorrectableConnectionFail(
                            "Was bounced. Debug call to reconnect"
                        ) from e
                    else:
                        raise CorrectableConnectionFail(
                            "Connection failed unexpectably. Reconnectable."
                        ) from e

                except Exception as e:
                    print("Unhandled exception in websocket", e)
                    logger.error("Websocket excepted closed definetely", exc_info=True)
                    logger.critical("Unhandled exception... ", exc_info=True)
                    raise DefiniteConnectionFail(e) from e

                finally:
                    if send_task:
                        send_task.cancel()
                        try:
                            await send_task
                        except asyncio.CancelledError:
                            pass
                    self._healthy = False

            except CorrectableConnectionFail as e:
                logger.info(f"Trying to Recover from Exception {e}")
                if retry > self.max_retries or not self.allow_reconnect:
                    logger.error("Max retries reached. Giving up")
                    raise DefiniteConnectionFail("Exceeded Number of Retries")

                logger.info(f"Waiting for some time before retrying: {self.time_between_retries}")
                await asyncio.sleep(self.time_between_retries)
                logger.info("Retrying to connect")
                retry += 1
                continue

            except asyncio.CancelledError as e:
                logger.info("Websocket got cancelled. Trying to shutdown graceully")
                raise e

    async def sending(self, client: websockets.ClientConnection) -> None:
        """Send messages to the agent transport"""
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
        """Delay the action until the agent is connected"""
        assert self._send_queue, "Should be connected"
        logger.debug(">>>>> Sending message %s", action.model_dump_json())
        await self._send_queue.put(action.model_dump_json())

    async def asend(self, message: messages.FromAgentMessage) -> None:
        """Send a message to the agent"""
        await self.delayaction(message)

    async def adisconnect(self) -> None:
        """Disconnect the agent transport"""
        pass

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        """_summary_"""
        pass
