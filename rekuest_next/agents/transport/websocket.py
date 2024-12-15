from typing import Awaitable, Callable, Dict
import websockets
from rekuest_next.agents.transport.base import AgentTransport
import asyncio
import json
from rekuest_next.agents.transport.errors import (
    AgentTransportException,
)
from rekuest_next.messages import (
    Assign,
    OutMessage,
    Provide,
    Unprovide,
    Cancel,
    Init,
    Interrupt,
    MessageType,
    Message,
)
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
    CorrectableConnectionFail,
    DefiniteConnectionFail,
    AgentWasKicked,
    AgentIsAlreadyBusy,
    AgentWasBlocked,
)

logger = logging.getLogger(__name__)


async def token_loader():
    raise NotImplementedError(
        "Websocket transport does need a defined token_loader on Connection"
    )


KICK_CODE = 3001
BUSY_CODE = 3002
BLOCKED_CODE = 3003
BOUNCED_CODE = 3004

agent_error_codes = {
    KICK_CODE: AgentWasKicked,
    BUSY_CODE: AgentIsAlreadyBusy,
    BLOCKED_CODE: AgentWasBlocked,
}

agent_error_message = {
    KICK_CODE: "Agent was kicked by the server",
    BUSY_CODE: "Agent can't connect on this instance_id as another instance is already connected. Please kick the other instance first or use another instance_id",
    BLOCKED_CODE: "Agent was blocked by the server",
}


class WebsocketAgentTransport(AgentTransport):
    endpoint_url: str
    ssl_context: ssl.SSLContext = Field(
        default_factory=lambda: ssl.create_default_context(cafile=certifi.where())
    )
    token_loader: Callable[[], Awaitable[str]] = Field(exclude=True)
    max_retries: int = 5
    time_between_retries: float = 3
    allow_reconnect: bool = True
    auto_connect: bool = True

    _futures: Contextual[Dict[str, asyncio.Future]] = None
    _connected: ContextBool = False
    _healthy: ContextBool = False
    _send_queue: Contextual[asyncio.Queue] = None
    _connection_task: Contextual[asyncio.Task] = None
    _connected_future: Contextual[asyncio.Future] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def __aenter__(self):
        assert (
            self._callback is not None
        ), "Callback not set. Use set callback first to set it"
        self._futures = {}

        self._send_queue = asyncio.Queue()

    async def aconnect(self, instance_id: str):
        self._connected_future = asyncio.Future()
        self._connection_task = asyncio.create_task(self.websocket_loop(instance_id))
        self._connected = await self._connected_future

    async def on_definite_error(self, e: Exception):
        if not self._connected_future.done():
            self._connected_future.set_exception(e)
        else:
            return await self._callback.on_definite_error(e)

    async def abroadcast(self, *args, **kwargs):
        await self._callback.abroadcast(*args, **kwargs)

    async def on_agent_error(self, e: Exception):
        if not self._connected_future.done():
            self._connected_future.set_exception(e)
        else:
            return await self._callback.on_agent_error(e)

    async def on_correctable_error(self, e: Exception):
        return await self._callback.on_correctable_error(e)

    async def websocket_loop(self, instance_id: str, retry=0, reload_token=False):
        send_task = None
        receive_task = None
        try:
            try:
                token = await self.token_loader(force_refresh=reload_token)

                async with websockets.connect(
                    f"{self.endpoint_url}",
                    ssl=(
                        self.ssl_context
                        if self.endpoint_url.startswith("wss")
                        else None
                    ),
                ) as client:
                    retry = 0
                    logger.info("Agent on Websockets connected")

                    await client.send(
                        json.dumps(
                            {
                                "type": "INITIAL",
                                "token": token,
                                "instance_id": instance_id,
                            }
                        )
                    )

                    send_task = asyncio.create_task(self.sending(client))
                    receive_task = asyncio.create_task(self.receiving(client))

                    self._healthy = True
                    done, pending = await asyncio.wait(
                        [send_task, receive_task],
                        return_when=asyncio.FIRST_EXCEPTION,
                    )
                    self._healthy = False

                    for task in pending:
                        task.cancel()

                    for task in done:
                        raise task.exception()

            except InvalidHandshake as e:
                logger.warning(
                    (
                        "Websocket to"
                        f" {self.endpoint_url}?token={token}&instance_id={instance_id} was"
                        " denied. Trying to reload token"
                    ),
                    exc_info=True,
                )
                reload_token = True
                raise CorrectableConnectionFail from e

            except ConnectionClosedError as e:
                logger.warning("Websocket was closed", exc_info=True)
                if e.code in agent_error_codes:
                    await self.on_agent_error(
                        agent_error_codes[e.code](agent_error_message[e.code])
                    )
                    raise AgentTransportException("Agent Error") from e

                if e.code == BOUNCED_CODE:
                    raise CorrectableConnectionFail(
                        "Was bounced. Debug call to reconnect"
                    ) from e

                else:
                    raise CorrectableConnectionFail(
                        "Connection failed unexpectably. Reconnectable."
                    ) from e

            except Exception as e:
                logger.error("Websocket excepted closed definetely", exc_info=True)
                await self.on_definite_error(DefiniteConnectionFail(str(e)))
                logger.critical("Unhandled exception... ", exc_info=True)
                raise DefiniteConnectionFail from e

        except CorrectableConnectionFail as e:
            logger.info(f"Trying to Recover from Exception {e}")

            should_retry = await self._callback.on_correctable_error(e)

            if retry > self.max_retries or not self.allow_reconnect or not should_retry:
                logger.error("Max retries reached. Giving up")
                raise DefiniteConnectionFail("Exceeded Number of Retries")

            logger.info(
                f"Waiting for some time before retrying: {self.time_between_retries}"
            )
            await asyncio.sleep(self.time_between_retries)
            logger.info("Retrying to connect")
            await self.websocket_loop(
                instance_id, retry=retry + 1, reload_token=reload_token
            )

        except asyncio.CancelledError as e:
            logger.info("Websocket got cancelled. Trying to shutdown graceully")
            if send_task and receive_task:
                send_task.cancel()
                receive_task.cancel()

            await asyncio.gather(send_task, receive_task, return_exceptions=True)
            raise e

    async def sending(self, client):
        try:
            while True:
                message = await self._send_queue.get()
                logger.info(f">>>> {message}")
                await client.send(message)
                self._send_queue.task_done()
        except asyncio.CancelledError:
            logger.info("Sending Task sucessfully Cancelled")

    async def receiving(self, client):
        try:
            async for message in client:
                logger.info(f"Receiving message {message}")
                await self.receive(message)

        except asyncio.CancelledError:
            logger.info("Receiving Task sucessfully Cancelled")

    async def receive(self, message):
        json_dict = json.loads(message)
        logger.debug(f"<<<< {message}")
        if "type" in json_dict:
            type = json_dict["type"]

            if type == MessageType.HEARTBEAT:
                await self._send_queue.put(json.dumps({"type": "HEARTBEAT"}))

            # State Layer
            if type == MessageType.INIT:
                initial_message = Init(**json_dict)

                if not self._connected_future.done():
                    self._connected_future.set_result(True)

                for i in initial_message.provisions:
                    await self.abroadcast(i)

                for i in initial_message.inquiries:
                    await self.abroadcast(i)

            if type == MessageType.ASSIGN:
                await self.abroadcast(Assign(**json_dict))

            if type == MessageType.CANCEL:
                await self.abroadcast(Cancel(**json_dict))

            if type == MessageType.UNPROVIDE:
                await self.abroadcast(Unprovide(**json_dict))

            if type == MessageType.PROVIDE:
                await self.abroadcast(Provide(**json_dict))

            if type == MessageType.INTERRUPT:
                await self.abroadcast(Interrupt(**json_dict))

        else:
            logger.error(f"Unexpected messsage: {json_dict}")

    async def awaitaction(self, action: Message):
        assert self._connected, "Should be connected"
        if action.id in self._futures:
            raise ValueError("Action already has a future")

        future = asyncio.Future()
        self._futures[action.id] = future
        await self._send_queue.put(action.json())
        return await future

    async def delayaction(self, action: Message):
        assert self._connected, "Should be connected"
        await self._send_queue.put(action.json())

    async def log_event(self, event: OutMessage):
        await self.delayaction(event)

    async def adisconnect(self):
        self._connection_task.cancel()
        self._connected = False

        try:
            await self._connection_task
        except:
            pass

        self._connection_task = None

    async def __aexit__(self, *args, **kwargs):
        if self._connection_task:
            await self.adisconnect()
