import asyncio
import logging
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Optional,
    Protocol,
    Union,
    runtime_checkable,
)
import uuid

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

from rekuest_next.actors.errors import UnknownMessageError
from rekuest_next.actors.transport.local_transport import ProxyActorTransport
from rekuest_next.actors.transport.types import ActorTransport, AssignTransport
from rekuest_next.actors.types import Passport
from rekuest_next.agents.errors import StateRequirementsNotMet
from rekuest_next.api.schema import (
    AssignationEventKind,
    Template,
)
from rekuest_next.collection.collector import (
    AssignationCollector,
    Collector,
)
from rekuest_next import messages
from rekuest_next.definition.define import DefinitionInput
from rekuest_next.structures.registry import (
    StructureRegistry
)
from rekuest_next.structures.default import (
    get_default_structure_registry
)
from rekuest_next.actors.sync import SyncGroup

logger = logging.getLogger(__name__)


@runtime_checkable
class Agent(Protocol):
    
    
    async def asend(self, actor: "Actor", message: messages.Assign) -> None: 
        ...
    





class Actor(BaseModel):
    agent: Agent
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_config = ConfigDict(arbitrary_types_allowed=True)
    collector: Collector = Field(default_factory=Collector)
    running_assignments: Dict[str, messages.Assign] = Field(default_factory=dict)
    sync: SyncGroup = Field(default_factory=SyncGroup)

    _in_queue: Optional[asyncio.Queue] = PrivateAttr(default=None)
    _running_asyncio_tasks: Dict[str, asyncio.Task] = PrivateAttr(default_factory=dict)
    _running_transports: Dict[str, AssignTransport] = PrivateAttr(default_factory=dict)
    _provision_task: asyncio.Task = PrivateAttr(default=None)
    _break_futures: Dict[str, asyncio.Future] = PrivateAttr(default_factory=dict)

    @model_validator(mode="before")
    def validate_sync(cls, values):
        """ A default syncgroup will be created if none is set"""
        if values.get("sync") is None:
            values["sync"] = SyncGroup()
        return values
    
    
    async def on_resume(self, resume: messages.Resume):
        """ A function that is called once the actor is resumed from a paused state.
        This can be used to re-initialize the actor after a pause.
        
        Args:
            resume (Resume): The resume message containing the information about the
                actor that was resumed.
        """
        if resume.assignation in self._break_futures:
            self._break_futures[resume.assignation].set_result(None)
            del self._break_futures[resume.assignation]
        else:
            logger.warning(
                f"Actor {self.id} was resumed but no break future was found for {resume.assignation}"
            )
        
    
    
    async def asend(
        self,
        message: messages.FromAgentMessage,
    ):
        """ A function to send a message to the agent. This is used to send messages
        to the agent from the actor.
        
        Args:
            transport (AssignTransport): The transport to use to send the message
            message (ToAgentMessage): The message to send
        """
        await self.agent.asend(self, message=message)
    
    
    async def on_pause(self, pause: messages.Pause):
        
        """ A function that is called once the actor is paused. This can be used to
        clean up resources or stop any ongoing tasks.
        
        Args:
            pause (Pause): The pause message containing the information about the
                actor that was paused.
        """
        if pause.assignation in self._break_futures:
            logger.warning(
                f"Actor {self.id} was paused but a break future was already set for {pause.assignation}"
            )
            return
        
        self._break_futures[pause.assignation] = asyncio.Future()
        
    
    
    async def on_step(self, step: messages.Step):
        """ A function that is called once the actor is asked to do a step,
        normally this should handle a resume following an immediate resume.
        
        Args:
            pause (Pause): The pause message containing the information about the
                actor that was stepped.
        """
        return None

    async def on_provide(self):
        """A function that is called once the actor is registered on the agent and we are
        getting in the provide loop. Here we can do some initialisation of the actor
        like start persisting database queries 
        
        Imaging this as the enter function of the async context manager
        
        Args:
            passport (Passport): The passport of the actor (provides some information on
                the actor like a unique local id for the actor)
        """
        return None

    async def on_unprovide(self):
        """ A function that is called once the actor is unregistered from the agent and we are
        getting out of the provide loop. Here we can do some finalisation of the actor
        like stop persisting database queries.
        
        Imagin this as the exit function of an async context manager.
        
        """
        return None

    async def on_assign(
        self,
        assignment: messages.Assign,
        collector: AssignationCollector,
        transport: AssignTransport,
    ):
        raise NotImplementedError(
            "Needs to be owerwritten in Actor Subclass. Never use this class directly"
        )

    async def aget_status(self):
        return self._status

    async def apass(self, message: messages.FromAgentMessage):
        assert self._in_queue, "Actor is currently not listening"
        await self._in_queue.put(message)

    async def arun(self):
        self._in_queue = asyncio.Queue()
        self._provision_task = asyncio.create_task(self.alisten())
        return self._provision_task

    async def acancel(self):
        # Cancel Mnaged actors
        logger.info(f"Cancelling Actor {self.id}")

        if not self._provision_task or self._provision_task.done():
            # Race condition
            return

        self._provision_task.cancel()

        try:
            await self._provision_task
        except asyncio.CancelledError:
            logger.info(f"Actor {self} was cancelled")
            

    async def abreak(self, assignation: str) -> bool:
        """Wait for the actor to be resumed or cancelled"""
        if assignation in self._break_futures:
            await self._break_futures[assignation]
            return True
        else:
            logger.warning(
                f"Currently no break future for {assignation} was found. Wasn't paused"
            )
            return False
    

    def assign_task_done(self, task):
        logger.info(f"Assign task is done: {task}")
        try:
            result = task.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Assign task {task} failed with exception {e}", exc_info=True)
        pass

    async def is_assignment_still_running(self, id: str) -> bool:
        if id in self._running_asyncio_tasks:
            return True
        return False

    async def aprocess(self, message: messages.ToAgentMessage):
        logger.info(f"Actor for {self.id}: Received {message}")

        if isinstance(message, messages.Assign):

            task = asyncio.create_task(
                self.on_assign(
                    message,
                )
            )

            task.add_done_callback(self.assign_task_done)
            self._running_asyncio_tasks[message.id] = task

        elif isinstance(message, messages.Cancel):
            if message.assignation in self._running_asyncio_tasks:
                task = self._running_asyncio_tasks[message.assignation]

                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        logger.info(
                            f"Task {message.assignation} was cancelled through arkitekt. Setting Cancelled"
                        )
                        await self.agent.asend(self, message=messages.CancelledEvent(assignation=message.assignation))
                       
                        del self._running_asyncio_tasks[message.id]
                        del self._running_transports[message.id]
                        await self.agent.asend(self, message=messages.CancelledEvent(assignation=message.assignation))

                else:
                    logger.warning(
                        "Race Condition: Task was already done before cancellation"
                    )
                    await self.agent.asend(self, message=messages.CancelledEvent(assignation=message.assignation))
                

            else:
                logger.error(
                    f"Actor for {self.passport}: Received unassignment for unknown assignation {message.id}"
                )
        else:
            raise UnknownMessageError(f"{message}")

    async def alisten(self):
        try:
            logger.info(f"Actor {self.id} Is now active")

            while True:
                message = await self._in_queue.get()
                try:
                    await self.aprocess(message)
                except Exception:
                    logger.critical(
                        "Processing unknown message should never happen", exc_info=True
                    )

        except asyncio.CancelledError:
            logger.info("Doing Whatever needs to be done to cancel!")

            [i.cancel() for i in self._running_asyncio_tasks.values()]

            for key, task in self._running_asyncio_tasks.items():
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info(
                        f"Task {key} was cancelled through applicaction. Setting Critical"
                    )
                    await self.agent.asend(
                        self, 
                        messages.CriticalEvent(
                            assignation=key,
                            error="Cancelled trhough application (this is not nice from the application and will be regarded as an error)",
                        )
                    )


        except Exception:
            logger.critical("Unhandled exception", exc_info=True)

            # TODO: Maybe send back an acknoledgement that we are done cancelling.
            # If we don't do this, arkitekt will not know if we failed to cancel our
            # tasks or if we succeeded. If we fail to cancel arkitekt can try to
            # kill the whole agent (maybe causing a sys.exit(1) or something)

        self._in_queue = None

    def _provision_task_done(self, task):
        logger.info(f"Provision task is done: {task}")
        if task.exception():
            raise task.exception()

    async def __aenter__(self):
        return self


    async def __aexit__(self, exc_type, exc, tb):
        if self._provision_task and not self._provision_task.done():
            await self.acancel()



class SerializingActor(Actor):
    definition: DefinitionInput = Field(description="The definition of the actor, describing what arguents and return values it provides")
    structure_registry: StructureRegistry = Field(default=get_default_structure_registry(), description="The structure regsistry to use for this actor")
    expand_inputs: bool = True
    shrink_outputs: bool = True
    state_variables: Dict[str, Any] = Field(default_factory=dict)
    context_variables: Dict[str, Any] = Field(default_factory=dict)
    contexts: Dict[str, Any] = Field(default_factory=dict)
    proxies: Dict[str, Any] = Field(default_factory=dict)

    async def add_local_variables(self, kwargs):
        for key, value in self.context_variables.items():
            try:
                kwargs[key] = self.contexts[value]
            except KeyError as e:
                raise StateRequirementsNotMet(f"State requirements not met: {e}") from e

        for key, value in self.state_variables.items():
            try:
                kwargs[key] = self.proxies[value]
            except KeyError as e:
                raise StateRequirementsNotMet(f"State requirements not met: {e}") from e

        return kwargs


Actor.model_rebuild()
SerializingActor.model_rebuild()
