from typing import Awaitable, Callable, Dict, Any
import websockets
from rekuest_next.agents.transport.base import AgentTransport
import asyncio
import json
from rekuest_next.agents.transport.errors import (
    AgentTransportException,
    AssignationListDeniedError,
    ProvisionListDeniedError,
)
from rekuest_next.agents.transport.protocols.agent_json import *
import logging
from websockets.exceptions import (
    ConnectionClosedError,
    InvalidStatusCode,
    InvalidHandshake,
)
from rekuest_next.api.schema import LogLevel
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
    max_retries = 5
    time_between_retries = 3
    allow_reconnect = True
    auto_connect = True

    _futures: Contextual[Dict[str, asyncio.Future]] = None
    _connected: ContextBool = False
    _healthy: ContextBool = False
    _send_queue: Contextual[asyncio.Queue] = None
    _connection_task: Contextual[asyncio.Task] = None
    _connected_future: Contextual[asyncio.Future]

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
                    f"{self.endpoint_url}?token={token}&instance_id={instance_id}",
                    ssl=(
                        self.ssl_context
                        if self.endpoint_url.startswith("wss")
                        else None
                    ),
                ) as client:
                    retry = 0
                    logger.info("Agent on Websockets connected")

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
                logger.debug(f">>>> {message}")
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
            id = json_dict["id"]

            # State Layer
            if type == AgentSubMessageTypes.HELLO:
                if not self._connected_future.done():
                    self._connected_future.set_result(True)

            if type == AgentSubMessageTypes.INQUIRY:
                await self.abroadcast(InquirySubMessage(**json_dict))

            if type == AgentSubMessageTypes.ASSIGN:
                await self.abroadcast(AssignSubMessage(**json_dict))

            if type == AgentSubMessageTypes.UNASSIGN:
                await self.abroadcast(UnassignSubMessage(**json_dict))

            if type == AgentSubMessageTypes.UNPROVIDE:
                await self.abroadcast(UnprovideSubMessage(**json_dict))

            if type == AgentSubMessageTypes.PROVIDE:
                await self.abroadcast(ProvideSubMessage(**json_dict))

            if type == AgentMessageTypes.LIST_PROVISIONS_REPLY:
                answer = ProvisionListReply(**json_dict)
                for prov in answer.provisions:
                    await self.abroadcast(ProvideSubMessage(**prov.dict()))

        else:
            logger.error(f"Unexpected messsage: {json_dict}")

    async def awaitaction(self, action: JSONMessage):
        assert self._connected, "Should be connected"
        if action.id in self._futures:
            raise ValueError("Action already has a future")

        future = asyncio.Future()
        self._futures[action.id] = future
        await self._send_queue.put(action.json())
        return await future

    async def delayaction(self, action: JSONMessage):
        assert self._connected, "Should be connected"
        await self._send_queue.put(action.json())

    async def list_provisions(
        self, exclude: Optional[ProvisionStatus] = None
    ) -> List[Provision]:
        action = ProvisionList(exclude=exclude)
        prov_list_reply: ProvisionListReply = await self.awaitaction(action)
        return prov_list_reply.provisions

    async def change_provision(
        self,
        id: str,
        status: ProvisionStatus = None,
        message: str = None,
        mode: ProvisionMode = None,
    ):
        action = ProvisionChangedMessage(
            provision=id, status=status, message=message, mode=mode
        )
        await self.delayaction(action)

    async def change_assignation(
        self,
        id: str,
        status: AssignationStatus = None,
        message: str = None,
        returns: List[Any] = None,
        progress: int = None,
    ):
        action = AssignationChangedMessage(
            assignation=id,
            status=status,
            message=message,
            returns=returns,
            progress=progress,
        )
        await self.delayaction(action)

    async def list_assignations(
        self, exclude: Optional[AssignationStatus] = None
    ) -> List[Assignation]:
        action = AssignationsList(exclude=exclude)
        ass_list_reply: AssignationsListReply = await self.awaitaction(action)
        return ass_list_reply.assignations

    async def log_to_assignation(
        self, id: str, level: LogLevel = None, message: str = None
    ):
        action = AssignationLogMessage(assignation=id, level=level, message=message)
        await self.delayaction(action)

    async def log_to_provision(
        self, id: str, level: LogLevel = None, message: str = None
    ):
        action = ProvisionLogMessage(provision=id, level=level, message=message)
        await self.delayaction(action)

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

    class Config:
        underscore_attrs_are_private = True
        arbitrary_types_allowed = True
        copy_on_model_validation = "none"
