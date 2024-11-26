

from rekuest_next.actors.base import Actor
from rekuest_next.actors.transport.types import ActorTransport
from rekuest_next.actors.types import Passport
from rekuest_next.agents.base import BaseAgent
from rekuest_next.agents.extension import BaseAgentExtension
import asyncio
from rekuest_next.actors.sync import SyncGroup
from rekuest_next.agents.extensions.delegating.actor import CLIActor
from rekuest_next.agents.extensions.delegating.protocol import In, InitMessage, InMessage, Out, OutMessage, StartRegistration, RegisterMessage, DoneRegistration
from rekuest_next.agents.extensions.delegating.transport import ProcessTransport
from rekuest_next.api.schema import Template, TemplateInput
from rekuest_next.collection.collector import Collector
from rekuest_next.definition.registry import DefinitionRegistry
from rekuest_next.structures.default import get_default_structure_registry
import logging


logger = logging.getLogger(__name__)



class CLIExtension(BaseAgentExtension):
    run_script: str
    magic_word: str = "#ARKITEKT"



    def __init__(self, run_script: str):
        self.run_script = run_script
        self.global_sync_group = SyncGroup()
        self.structure_registry = get_default_structure_registry()
        self.definition_registry = DefinitionRegistry()
        self.proc = None

    def get_name(self) -> str:
        return "cli"
    
    async def should_cleanup_on_init(self) -> bool:
        return True

    async def astart(self, instance_id: str):
        logger.debug("Starting CLI extension")
        self.proc = await asyncio.create_subprocess_shell(
            self.run_script,
            stdout=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            shell=True,
            
        )

        self.stdout_queue = asyncio.Queue()
        self.stderr_queue = asyncio.Queue()

        async def enqueue_output(stream, queue):
            while True:
                line = await stream.readline()
                if not line:
                    break
                try:
                    message = line.decode()
                    if message.startswith(self.magic_word):
                        logger.debug(f"Received message: {message}")
                        await queue.put(message)
                    else:
                        print(message)
                except Exception as e:
                    continue

        self.stdout_task = asyncio.create_task(enqueue_output(self.proc.stdout, self.stdout_queue))
        self.stderr_task = asyncio.create_task(enqueue_output(self.proc.stderr, self.stderr_queue))

        logger.info(f"Started process: {self.proc.pid} {self.run_script}")


        message = await self.aget_next_message(timeout=1)
        if not isinstance(message, InitMessage):
            raise Exception("Invalid message", message)
        
        logger.info(f"Received init message: {message.name}")




    def parse_message(self, message: str) -> InMessage:
        if message.startswith(self.magic_word):
            logger.debug(f"Received message: {message}")
            try:
                x =  In.model_validate_json(message[len(self.magic_word):])
                return x.message
            except Exception as e:
                logger.error(f"Failed to parse message: {e}")
                raise Exception(f"Failed to parse message {message[len(self.magic_word):]}") from e
        else:
            print(message)
        
        return None
        
    async def asend_message(self, message: OutMessage):

        clear_message = Out(message=message).model_dump_json()
        write = self.proc.stdin.write(f"{self.magic_word}{clear_message}\n".encode())
        await self.proc.stdin.drain()


    async def _aget_next_message_task(self) -> InMessage:
        while True:
            line = await self.stdout_queue.get()
            message = self.parse_message(line)
            if message:
                return message

    async def aget_next_message(self, timeout=None) -> InMessage | None:
        try:
            message = await asyncio.wait_for(self._aget_next_message_task(), timeout=timeout)
            return message
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError("Timeout waiting for message")

    async def aspawn_actor_from_template(self, template: Template, passport: Passport, transport: ActorTransport, agent: BaseAgent, collector: Collector) -> Actor | None:
       
        return CLIActor(
            process_transport=ProcessTransport(self),
            interface=template.interface,
            global_sync_group=self.global_sync_group,
            structure_registry=self.structure_registry,
            template=template,
            definition=self.definition_registry.get_definition_for_interface(template.interface),
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
            message = await self.aget_next_message(timeout=4)

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
        if self.proc:
            self.proc.terminate()
            try:
                return_code = await asyncio.wait_for(self.proc.wait(), timeout=1)
                logger.info(f"Process exited with {return_code}")
            except asyncio.TimeoutError:
                logger.warning("Process did not exit in time, killing it")
                self.proc.kill()
                return_code = await self.proc.wait()
                logger.warning(f"Process forcefully exited with {return_code}")
