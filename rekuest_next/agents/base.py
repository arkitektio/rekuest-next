import asyncio
import logging
from typing import Any, Dict, List, Optional

from pydantic import ConfigDict, Field

from koil import unkoil
from koil.composition import KoiledModel
from rekuest_next.actors.base import Actor
from rekuest_next.actors.transport.local_transport import (
    ProxyActorTransport,
)
from rekuest_next.actors.transport.types import ActorTransport
from rekuest_next.actors.types import Passport
from rekuest_next.agents.errors import AgentException, ProvisionException
from rekuest_next.agents.registry import ExtensionRegistry, get_default_extension_registry
from rekuest_next.agents.transport.base import AgentTransport, Contextual
from rekuest_next.api.schema import (
    AssignationEventKind,
    Template,
    aensure_agent,
    aset_extension_templates,
)
from rekuest_next.collection.collector import Collector
from rekuest_next import messages
from rekuest_next.rath import RekuestNextRath
from .transport.errors import CorrectableConnectionFail, DefiniteConnectionFail

logger = logging.getLogger(__name__)




class BaseAgent(KoiledModel):
    """Agent

    Agents are the governing entities for every app. They are responsible for
    managing the lifecycle of the direct actors that are spawned from them through arkitekt.

    Agents are nothing else than actors in the classic distributed actor model, but they are
    always provided when the app starts and they do not provide functionality themselves but rather
    manage the lifecycle of the actors that are spawned from them.

    The actors that are spawned from them are called guardian actors and they are the ones that+
    provide the functionality of the app. These actors can then in turn spawn other actors that
    are not guardian actors. These actors are called non-guardian actors and their lifecycle is
    managed by the guardian actors that spawned them. This allows for a hierarchical structure
    of actors that can be spawned from the agents.


    """

    name: str
    instance_id: str = "main"
    rath: RekuestNextRath
    transport: AgentTransport
    extension_registry: ExtensionRegistry = Field(
        default_factory=get_default_extension_registry
    )
    managed_actors: Dict[str, Actor] = Field(default_factory=dict)
    interface_template_map: Dict[str, Template] = Field(default_factory=dict)
    template_interface_map: Dict[str, str] = Field(default_factory=dict)
    provision_passport_map: Dict[int, Passport] = Field(default_factory=dict)
    managed_assignments: Dict[str, messages.Assign] = Field(default_factory=dict)
    running_assignments: Dict[str, str] = Field(
        default_factory=dict, description="Maps assignation to actor id"
    )
    _inqueue: Contextual[asyncio.Queue] = None
    _errorfuture: Contextual[asyncio.Future] = None
    _contexts: Dict[str, Any] = None
    _states: Dict[str, Any] = None

    started: bool = False
    running: bool = False
    model_config = ConfigDict(arbitrary_types_allowed=True)


    async def abroadcast(self, message: messages.ToAgentMessage) -> None:
        await self._inqueue.put(message)

    async def on_agent_error(self, exception) -> None:
        if self._errorfuture is None or self._errorfuture.done():
            return
        self._errorfuture.set_exception(exception)
        ...

    async def on_definite_error(self, error: DefiniteConnectionFail) -> None:
        if self._errorfuture is None or self._errorfuture.done():
            return
        self._errorfuture.set_exception(error)
        ...

    async def on_correctable_error(self, error: CorrectableConnectionFail) -> bool:
        # Always correctable
        return True
        ...

    async def process(self, message: messages.ToAgentMessage) -> None:
        logger.info(f"Agent received {message}")

        if isinstance(message, messages.Assign):
            if message.actor_id in self.managed_actors:
                actor = self.managed_actors[message.actor_id]
                self.managed_assignments[message.assignation] = message
                await actor.apass(message)
            else:
                try:
                    
                    actor = await self.aspawn_actor_from_assign(
                        message 
                    )
                    
                    await actor.apass(message)
                    
                    
                except Exception as e:
                   await self.transport.asend(
                        messages.CriticalEvent(
                            assignation=message.assignation,
                            error=f"Not able to create actor through extensions {str(e)}",
                        )
                    )
                   raise e
               

        elif isinstance(message, (messages.Cancel, messages.Step, messages.Collect)):
            if message.assignation in self.managed_assignments:
                assignment = self.managed_assignments[message.assignation]
                actor = self.managed_actors[assignment.actor_id]
                await actor.apass(message)
            else:
                logger.warning(
                    "Received unassignation for a provision that is not running"
                    f"Managed: {self.provision_passport_map} Received: {message.provision}"
                )
                await self.transport.asend(
                   messages.CriticalEvent(
                        assignation=message.assignation,
                        error="Actors is no longer running and not managed. Probablry there was a restart",
                   )
                )

        elif isinstance(message, messages.AssignInquiry):
            if message.assignation in self.managed_assignments:
                assignment = self.managed_assignments[message.assignation]
                actor = self.managed_actors[assignment.actor_id]

                # Checking status
                status = await actor.is_assignment_still_running(assignment)
                if status:
                    await self.transport.asend(
                        messages.ProgressEvent(
                            assignation=message.assignation,
                            message="Actor is still running",
                        )
                    )
                else:
                    await self.transport.asend(
                        messages.CriticalEvent(
                            assignation=message.assignation,
                            error="The assignment was not running anymore. But the actor was still managed. This could lead to some race conditions",
                        )
                    )
            else:
                await self.transport.asend(
                     messages.CriticalEvent(
                        assignation=message.assignation,
                        error="After disconnect actor was no longer managed (probably the app was restarted)",
                    )
                )

        

        else:
            raise AgentException(f"Unknown message type {type(message)}")

    async def atear_down(self):
        cancelations = [actor.acancel() for actor in self.managed_actors.values()]
        # just stopping the actor, not cancelling the provision..

        for c in cancelations:
            try:
                await c
            except asyncio.CancelledError:
                pass

        if self._errorfuture is not None and not self._errorfuture.done():
            self._errorfuture.cancel()
            try:
                await self._errorfuture
            except asyncio.CancelledError:
                pass

        for extension in self.extension_registry.agent_extensions.values():
            await extension.atear_down()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.atear_down()
        await self.transport.__aexit__(exc_type, exc_val, exc_tb)


    async def aregister_definitions(self, instance_id: Optional[str] = None):
        """Registers the definitions that are defined in the definition registry

        This method is called by the agent when it starts and it is responsible for
        registering the definitions that are defined in the definition registry. This
        is done by sending the definitions to arkitekt and then storing the templates
        that are returned by arkitekt in the agent's internal data structures.

        You can implement this method in your agent subclass if you want define preregistration
        logic (like registering definitions in the definition registry).
        """

        x = await aensure_agent(
            instance_id=instance_id,
            name=self.name,
            extensions=[extension.get_name() for extension in self.extension_registry.agent_extensions.values()],
        )

        for extension_name, extension in self.extension_registry.agent_extensions.items():
            to_be_created_templates = await extension.aget_templates()

            created_templates = await aset_extension_templates(
                templates=to_be_created_templates,
                run_cleanup=extension.cleanup,
                instance_id=instance_id,
                extension=extension_name,
            )
            
            

            for template in created_templates:
                self.interface_template_map[template.interface] = template
                self.template_interface_map[template.id] = template


    async def afind_local_template_for_nodehash(
        self, nodehash: str
    ) -> Optional[Template]:
        for template in self.interface_template_map.values():
            if template.node.hash == nodehash:
                return template
            
            
    async def asend(self, actor: "Actor", message: messages.FromAgentMessage) -> None:
        """Sends a message to the actor. This is used for sending messages to the
        agent from the actor. The agent will then send the message to the transport.
        """
        await self.transport.asend(message)


    async def astart(self, instance_id: Optional[str] = None):
        instance_id = self.instance_id

        for extension in self.extension_registry.agent_extensions.values():
            await extension.astart(instance_id)

        await self.aregister_definitions(instance_id=instance_id)

        self._errorfuture = asyncio.Future()
        await self.transport.aconnect(instance_id)


    async def aspawn_actor_from_assign(self, assign: messages.Assign) -> Actor:
        """Spawns an Actor from a Provision. This function closely mimics the
        spawining protocol within an actor. But maps template"""


        if assign.extension not in self.extension_registry.agent_extensions:
            raise ProvisionException(
                f"Extension {assign.extension} not found in agent {self.name}"
            )
        extension = self.extension_registry.agent_extensions[assign.extension]
        
        actor = await extension.aspawn_actor_for_interface(self, assign.interface)

        await actor.arun()  # TODO: Maybe move this outside?
        self.managed_actors[assign.actor_id] = actor
        self.managed_assignments[assign.assignation] = assign

        return actor

    async def await_errorfuture(self):
        return await self._errorfuture

    async def astep(self):
        queue_task = asyncio.create_task(self._inqueue.get(), name="queue_future")
        error_task = asyncio.create_task(self.await_errorfuture(), name="error_future")
        done, pending = await asyncio.wait(
            [queue_task, error_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        if self._errorfuture.done():
            raise self._errorfuture.exception()
        else:
            await self.process(await done.pop())

    def step(self, *args, **kwargs):
        return unkoil(self.astep, *args, **kwargs)

    def start(self, *args, **kwargs):
        return unkoil(self.astart, *args, **kwargs)

    def provide(self, *args, **kwargs):
        return unkoil(self.aprovide, *args, **kwargs)

    async def aloop(self):
        try:
            while True:
                self.running = True
                await self.astep()
        except asyncio.CancelledError:
            logger.info(
                "Provisioning task cancelled. We are running" f" {self.transport}"
            )
            self.running = False
            raise

    async def aprovide(self, instance_id: Optional[str] = None):
        try:
            logger.info(
                f"Launching provisioning task. We are running {self.transport.instance_id}"
            )
            await self.astart(instance_id=instance_id)
            logger.info("Starting to listen for requests")
            await self.aloop()
        except asyncio.CancelledError:
            logger.info("Provisioning task cancelled. We are running")
            await self.atear_down()
            raise

    async def __aenter__(self):
        self._inqueue = asyncio.Queue()
        self.transport.set_callback(self)
        await self.transport.__aenter__()
        return self
