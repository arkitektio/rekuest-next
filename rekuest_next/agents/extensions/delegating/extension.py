from pydantic import BaseModel, Field, ConfigDict
from rekuest_next.actors.base import Actor
from rekuest_next.actors.transport.types import ActorTransport
from rekuest_next.actors.types import Passport
from rekuest_next.agents.base import BaseAgent
from typing import Callable, Awaitable, Optional
import asyncio
from rekuest_next.actors.sync import SyncGroup
from rekuest_next.agents.extensions.delegating.actor import CLIActor
from rekuest_next.agents.extensions.delegating.protocol import (
    In,
    InitMessage,
    InMessage,
    Out,
    OutMessage,
    StartRegistration,
    RegisterMessage,
    DoneRegistration,
)
from rekuest_next.agents.extensions.delegating.transport import ProcessTransport
from rekuest_next.api.schema import Template, TemplateInput
from rekuest_next.collection.collector import Collector
from rekuest_next.definition.registry import DefinitionRegistry
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.structures.default import get_default_structure_registry
import logging
import re

logger = logging.getLogger(__name__)


class ProcessHandle:

    def __init__(self, proc: asyncio.subprocess.Process, _):
        self.proc = proc

    async def write(self, message, end_with="\n"):
        if not isinstance(message, bytes):
            message = (message + end_with).encode()

        self.proc.stdin.write(message)
        await self.proc.stdin.drain()

    async def read(self, until: str = "\n") -> str:
        buffer = bytearray()
        while True:
            char = await self.proc.stdout.read(1)
            if not char:  # EOF
                break

            buffer.extend(char)
            if buffer.decode().endswith(until):
                break
        return buffer.decode()


magic_message = re.compile(r".*#ARKITEKT\|\|(.*)\|\|().*")


class CLIExtension(BaseModel):
    run_script: str
    magic_word: str = "#ARKITEKT"
    global_sync_group: SyncGroup = Field(default_factory=SyncGroup)
    structure_registry: StructureRegistry = Field(
        default_factory=get_default_structure_registry
    )
    definition_registry: DefinitionRegistry = Field(default_factory=DefinitionRegistry)
    on_init: Optional[Callable[[ProcessHandle], Awaitable[None]]] = None
    model_config = ConfigDict(arbitrary_types_allowed=True)
    on_process_stdout: Optional[Callable[[str], Awaitable[None]]] = None
    initial_timeout: int = 10
    retrieve_timeout: int = 4

    _proc: asyncio.Queue = None
    _stdout_queue: asyncio.Queue = None
    _stderr_queue: asyncio.Queue = None
    _stdout_task: asyncio.Task = None
    _stderr_task: asyncio.Task = None

    def get_name(self) -> str:
        return "cli"

    async def should_cleanup_on_init(self) -> bool:
        return True

    async def astart(self, instance_id: str):
        logger.debug("Starting CLI extension")
        self._proc = await asyncio.create_subprocess_shell(
            self.run_script,
            stdout=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            shell=True,
        )

        self._stdout_queue = asyncio.Queue()
        self._stderr_queue = asyncio.Queue()

        async def enqueue_output(stream, queue):
            while True:
                line = await stream.readline()
                try:
                    message = line.decode()
                    if not message:
                        continue

                    g = magic_message.match(message)

                    if self.on_process_stdout:
                        await self.on_process_stdout(message)
                    if g:
                        trimmed_message = g.group(1)
                        logger.debug(f"Received message: {message}")

                        await queue.put(trimmed_message)
                    else:
                        if message.endswith("\n"):
                            message = message[:-1]

                        print(message)
                except Exception:
                    continue

        if self.on_init:
            await self.on_init(ProcessHandle(self._proc, self._stdout_queue))

        self._stdout_task = asyncio.create_task(
            enqueue_output(self._proc.stdout, self._stdout_queue)
        )
        self._stderr_task = asyncio.create_task(
            enqueue_output(self._proc.stderr, self._stdout_queue)
        )

        logger.info(f"Started process: {self._proc.pid} {self.run_script}")

        message = await self.aget_next_message(timeout=self.initial_timeout)
        if not isinstance(message, InitMessage):
            raise Exception("Invalid message", message)

        logger.info(f"Received init message: {message.name}")

    def parse_message(self, message: str) -> InMessage:
        logger.debug(f"Received message: {message}")
        try:
            x = In.model_validate_json(message)
            return x.message
        except Exception as e:
            logger.error(f"Failed to parse message: {e}")
            raise Exception(f"Failed to parse message {message}") from e

    async def asend_message(self, message: OutMessage):

        clear_message = Out(message=message).model_dump_json()
        write = self._proc.stdin.write(f"{self.magic_word}{clear_message}\n".encode())
        await self._proc.stdin.drain()

    async def _aget_next_message_task(self) -> InMessage:
        while True:
            line = await self._stdout_queue.get()
            message = self.parse_message(line)
            if message:
                return message

    async def aget_next_message(self, timeout=None) -> Optional[InMessage]:
        try:
            message = await asyncio.wait_for(
                self._aget_next_message_task(), timeout=timeout
            )
            return message
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError("Timeout waiting for message")

    async def aspawn_actor_from_template(
        self,
        template: Template,
        passport: Passport,
        transport: ActorTransport,
        agent: BaseAgent,
        collector: Collector,
    ) -> Optional[Actor]:

        return CLIActor(
            process_transport=ProcessTransport(self),
            interface=template.interface,
            global_sync_group=self.global_sync_group,
            structure_registry=self.structure_registry,
            template=template,
            definition=self.definition_registry.get_definition_for_interface(
                template.interface
            ),
            passport=passport,
            transport=transport,
            collector=collector,
            agent=agent,
        )

    async def aretrieve_registry(self):

        await self.asend_message(StartRegistration())

        # get new lines until magic word
        while True:
            logger.info("Waiting for messages")
            message = await self.aget_next_message(timeout=self.retrieve_timeout)

            if isinstance(message, RegisterMessage):

                self.definition_registry.register_at_interface(
                    message.interface,
                    template=TemplateInput(
                        definition=message.definition,
                        interface=message.interface,
                        dependencies=[],
                        dynamic=False,
                    ),
                    structure_registry=self.structure_registry,
                    actorBuilder=None,
                )
                logger.info(f"Registered {message.interface}")

            elif isinstance(message, DoneRegistration):
                break

            else:
                raise Exception("Invalid message", message)

        logger.info("Done registering")
        return self.definition_registry

    async def atear_down(self):
        self.definition_registry = None
        logger.info("Tearing down")
        if self._proc:
            try:
                self._proc.terminate()
                try:
                    return_code = await asyncio.wait_for(self._proc.wait(), timeout=1)
                    logger.info(f"Process exited with {return_code}")
                except asyncio.TimeoutError:
                    logger.warning("Process did not exit in time, killing it")
                    self._proc.kill()
                    return_code = await self._proc.wait()
                    logger.warning(f"Process forcefully exited with {return_code}")
            except ProcessLookupError:
                logger.warning("Process already exited")
