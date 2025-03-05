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
    ProvisionEventKind,
    Template,
    aget_provision,
    aensure_agent,
    aset_extension_templates,
)
from rekuest_next.collection.collector import Collector
from rekuest_next.messages import (
    Assign,
    InMessage,
    Cancel,
    Interrupt,
    Provide,
    Unprovide,
    AssignationEvent,
    AssignInquiry,
    ProvisionEvent,
)
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
    collector: Collector = Field(default_factory=Collector)
    managed_actors: Dict[str, Actor] = Field(default_factory=dict)
    interface_template_map: Dict[str, Template] = Field(default_factory=dict)
    template_interface_map: Dict[str, str] = Field(default_factory=dict)
    provision_passport_map: Dict[int, Passport] = Field(default_factory=dict)
    managed_assignments: Dict[str, Assign] = Field(default_factory=dict)
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


    async def abroadcast(self, message: InMessage):
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

    async def process(self, message: InMessage):
        logger.info(f"Agent received {message}")

        if isinstance(message, Assign):
            if message.provision in self.provision_passport_map:
                passport = self.provision_passport_map[message.provision]
                actor = self.managed_actors[passport.id]

                # Converting assignation to Assignment
                message = Assign(
                    assignation=message.assignation,
                    args=message.args,
                    user=message.user,
                    context={},
                )

                self.managed_assignments[message.assignation] = message
                self.running_assignments[message.assignation] = passport.id
                await actor.apass(message)
            else:
                logger.warning(
                    "Received assignation for a provision that is not running"
                    f"Managed: {self.provision_passport_map} Received: {message.provision}"
                )
                await self.transport.log_event(
                    AssignationEvent(
                        assignation=message.assignation,
                        kind=AssignationEventKind.CRITICAL,
                        message="Actor was no longer running or not managed",
                    )
                )

        elif isinstance(message, Interrupt):
            if message.assignation in self.managed_assignments:
                passport = self.provision_passport_map[message.provision]
                actor = self.managed_actors[passport.id]
                assignment = self.managed_assignments[message.assignation]

                # Converting unassignation to unassignment
                unass = Cancel(assignation=message.assignation, id=assignment.id)

                await actor.apass(unass)
            else:
                logger.warning(
                    "Received unassignation for a provision that is not running"
                    f"Managed: {self.provision_passport_map} Received: {message.provision}"
                )
                await self.transport.log_event(
                    AssignationEvent(
                        assignation=message.assignation,
                        kind=AssignationEventKind.CRITICAL,
                        message="Actor could not be interupted because it was no longer running or not managed",
                    )
                )

        elif isinstance(message, AssignInquiry):
            if message.assignation in self.managed_assignments:
                passport = self.provision_passport_map[message.provision]
                actor = self.managed_actors[passport.id]
                assignment = self.managed_assignments[message.assignation]

                # Checking status
                status = await actor.is_assignment_still_running(assignment)
                if status:
                    await self.transport.log_event(
                        AssignationEvent(
                            assignation=message.assignation,
                            kind=AssignationEventKind.PROGRESS,
                            message="Actor is still running",
                        )
                    )
                else:
                    await self.transport.log_event(
                        AssignationEvent(
                            assignation=message.assignation,
                            kind=AssignationEventKind.CRITICAL,
                            message="After disconnect actor was no longer running (app was however still running)",
                        )
                    )
            else:
                await self.transport.log_event(
                    AssignationEvent(
                        assignation=message.assignation,
                        kind=AssignationEventKind.CRITICAL,
                        message="After disconnect actor was no longer managed (probably the app was restarted)",
                    )
                )

        elif isinstance(message, Cancel):
            if message.assignation in self.running_assignments:
                actor_id = self.running_assignments[message.assignation]
                actor = self.managed_actors[actor_id]
                assignment = self.managed_assignments[message.assignation]

                # Converting unassignation to unassignment
                unass = Cancel(
                    assignation=message.assignation,
                    id=assignment.id,
                    context={},
                )

                await actor.apass(unass)
            else:
                logger.warning(
                    "Received unassignation for a provision that is not running"
                    f"Managed: {self.provision_passport_map} Received: {message}"
                )
                await self.transport.log_event(
                    AssignationEvent(
                        assignation=message.assignation,
                        kind=AssignationEventKind.CRITICAL,
                        message="Actor could not be canceled because it was no longer running or not managed",
                    )
                )

        elif isinstance(message, Provide):
            # TODO: Check if the provision is already running
            try:
                status = await self.acheck_status_for_provision(message)
                await self.transport.log_event(
                    ProvisionEvent(
                        provision=message.provision,
                        kind=ProvisionEventKind.ACTIVE,
                        message=f"Actor was already running {message}",
                    )
                )
            except KeyError:
                try:
                    await self.aspawn_actor_from_provision(message)
                except ProvisionException:
                    logger.error(
                        f"Error when spawing Actor for {message}", exc_info=True
                    )
                    await self.transport.log_event(
                        ProvisionEvent(
                            provision=message.provision,
                            kind=ProvisionEventKind.CRITICAL,
                            message=f"Error when spawing Actor for {message}",
                        )
                    )

        elif isinstance(message, Unprovide):
            if message.provision in self.provision_passport_map:
                passport = self.provision_passport_map[message.provision]
                actor = self.managed_actors[passport.id]
                await actor.acancel()
                await self.transport.log_event(
                    ProvisionEvent(
                        provision=message.provision,
                        kind=ProvisionEventKind.UNHAPPY,
                        message="Actor was sucessfully unprovided",
                    )
                )
                del self.provision_passport_map[message.provision]
                del self.managed_actors[passport.id]
                logger.info("Actor stopped")

            else:
                await self.transport.log_event(
                    ProvisionEvent(
                        provision=message.provision,
                        kind=ProvisionEventKind.CRITICAL,
                        message="Received Unprovision for never provisioned provision",
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
            definition_registry = extension.get_definition_registry()
            run_cleanup = extension.should_cleanup_on_init()

            to_be_created_templates = tuple(definition_registry.templates.values())

            created_templates = await aset_extension_templates(
                templates=to_be_created_templates,
                run_cleanup=run_cleanup,
                instance_id=instance_id,
                extension=extension_name,
            )

            for template in created_templates:
                self.interface_template_map[template.interface] = template
                self.template_interface_map[template.id] = template

    async def acheck_status_for_provision(self, provide: Provide) -> ProvisionEventKind:
        passport = self.provision_passport_map[provide.provision]
        actor = self.managed_actors[passport.id]
        return await actor.aget_status()

    async def afind_local_template_for_nodehash(
        self, nodehash: str
    ) -> Optional[Template]:
        for template in self.interface_template_map.values():
            if template.node.hash == nodehash:
                return template

    async def abuild_actor_for_template(
        self, template: Template, passport: Passport, transport: ActorTransport
    ) -> Actor:
        if not template.extension:
            raise ProvisionException(
                "No extension specified. This should not happen with the current implementation"
            )

        try:
            extension = self.extension_registry.agent_extensions[template.extension]

            actor = await extension.aspawn_actor_from_template(
                template=template,
                passport=passport,
                transport=transport,
                agent=self,
                collector=self.collector,
            )
        except Exception as e:
            raise ProvisionException("Error spawning actor from extension") from e

        if not actor:
            raise ProvisionException("No extensions managed to spawn an actor")

        return actor

    async def astart(self, instance_id: Optional[str] = None):
        instance_id = self.instance_id

        for extension in self.extension_registry.agent_extensions.values():
            await extension.astart(instance_id)

        await self.aregister_definitions(instance_id=instance_id)

        self._errorfuture = asyncio.Future()
        await self.transport.aconnect(instance_id)

    async def on_assign_change(self, assignment: Assign, *args, **kwargs):
        await self.transport.change_assignation(assignment.assignation, *args, **kwargs)

    async def on_assign_log(self, assignment: Assign, *args, **kwargs):
        await self.transport.log_to_assignation(assignment.assignation, *args, **kwargs)

    async def on_actor_change(self, passport: Passport, *args, **kwargs):
        await self.transport.change_provision(passport.provision, *args, **kwargs)

    async def on_actor_log(self, passport: Passport, *args, **kwargs):
        await self.transport.log_to_provision(passport.provision, *args, **kwargs)

    async def aspawn_actor_from_provision(self, provide_message: Provide) -> Actor:
        """Spawns an Actor from a Provision. This function closely mimics the
        spawining protocol within an actor. But maps template"""

        if provide_message.provision in self.provision_passport_map:
            logger.warning("Received provision for a provision that is already running")
            return

        try:
            provision = await aget_provision(
                provide_message.provision,
                rath=self.rath,
            )

        except Exception as e:
            print(e)
            logger.error(
                f"Error when getting provision for {provide_message}", exc_info=True
            )
            return

        passport = Passport(provision=provision.id, instance_id=self.instance_id)

        transport = ProxyActorTransport(
            passport=passport,
            on_log_event=self.transport.log_event,
        )

        actor = await self.abuild_actor_for_template(
            provision.template, passport, transport
        )

        await actor.arun()  # TODO: Maybe move this outside?
        self.managed_actors[actor.passport.id] = actor
        self.provision_passport_map[int(provision.id)] = (
            actor.passport
        )  # TODO: This should be a passport

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
