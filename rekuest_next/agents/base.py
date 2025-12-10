"""Base agent class

This is the base class for all agents. It provides the basic functionality
for managing the lifecycle of the actors that are spawned from it.

"""

import asyncio
import logging
from types import TracebackType
from typing import Any, Dict, Optional, Self
import uuid

from pydantic import ConfigDict, Field, PrivateAttr


from rekuest_next.api.schema import (
    State,
    StateSchemaInput,
    acreate_state_schema,
    aget_implementation,
    aset_agent_states,
    StateImplementationInput,
    StateSchema,
)
import jsonpatch  # type: ignore[import-untyped]
from koil import unkoil
from koil.composition import KoiledModel
from rekuest_next.actors.types import Passport, Actor
from rekuest_next.agents.errors import AgentException, ProvisionException
from rekuest_next.agents.hooks.registry import (
    HooksRegistry,
    StartupHookReturns,
    get_default_hook_registry,
)
from rekuest_next.agents.registry import (
    ExtensionRegistry,
    get_default_extension_registry,
)
from rekuest_next.state.shrink import ashrink_state
from rekuest_next.agents.transport.types import AgentTransport
from rekuest_next.api.schema import (
    Implementation,
    Agent,
    aensure_agent,
    ashelve,
    aunshelve,
    aset_extension_implementations,
)
from rekuest_next import acall, messages
from rekuest_next.protocols import AnyState
from rekuest_next.rath import RekuestNextRath
from rekuest_next.scalars import Identifier
from rekuest_next.state.proxies import StateProxy
from rekuest_next.state.registry import StateRegistry, get_default_state_registry
from rekuest_next.structures.types import JSONSerializable
from .transport.errors import (
    AgentTransportException,
    CorrectableConnectionFail,
    DefiniteConnectionFail,
)

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

    rath: RekuestNextRath = Field(
        description="The graph client that is used to make queries to when connecting to the rekuest server.",
    )

    name: str = Field(
        default="BaseAgent",
        description="The name of the agent. This is used to identify the agent in the system.",
    )
    instance_id: str = Field(
        default="default",
        description="The instance id of the agent. This is used to identify the agent in the system.",
    )
    shelve: Dict[str, Any] = Field(default_factory=dict)
    transport: AgentTransport
    extension_registry: ExtensionRegistry = Field(
        default_factory=get_default_extension_registry
    )
    state_registry: StateRegistry = Field(
        default_factory=get_default_state_registry,
        description="A global registry of all registered states for this extension. Think @state",
    )
    hook_registry: HooksRegistry = Field(
        default_factory=get_default_hook_registry,
        description="The hooks registry for this extension. Think @startup and @background",
    )
    proxies: Dict[str, StateProxy] = Field(default_factory=dict)
    contexts: Dict[str, Any] = Field(default_factory=dict)
    states: Dict[str, AnyState] = Field(
        default_factory=dict,
        description="Maps the state key to the state value. This is used to store the states of the agent.",
    )
    capture_condition: asyncio.Condition = Field(default_factory=asyncio.Condition)
    capture_active: bool = Field(default=False)

    managed_actors: Dict[str, Actor] = Field(default_factory=dict)
    interface_implementation_map: Dict[str, Implementation] = Field(
        default_factory=dict
    )
    implementation_interface_map: Dict[str, str] = Field(default_factory=dict)
    provision_passport_map: Dict[int, Passport] = Field(default_factory=lambda: {})
    managed_assignments: Dict[str, messages.Assign] = Field(default_factory=dict)
    running_assignments: Dict[str, str] = Field(
        default_factory=dict, description="Maps assignation to actor id"
    )
    managed_actor_tasks: Dict[str, asyncio.Task[None]] = Field(
        default_factory=dict,
        description="Maps actor id to the task that is running the actor",
    )

    _errorfuture: Optional[asyncio.Future[Exception]] = None
    _agent: Optional[Agent] = None

    _current_shrunk_states: Dict[str, JSONSerializable] = PrivateAttr(
        default_factory=lambda: {}  # type: ignore[return-value]
    )
    _shrunk_states: Dict[str, Any] = PrivateAttr(default_factory=lambda: {})
    _interface_stateschema_map: Dict[str, StateSchema] = PrivateAttr(
        default_factory=lambda: {}  # typ
    )
    _interface_stateschema_input_map: Dict[str, StateSchemaInput] = PrivateAttr(
        default_factory=lambda: {}  # typ
    )

    _background_tasks: Dict[str, asyncio.Task[None]] = PrivateAttr(
        default_factory=lambda: {}
    )

    started: bool = False
    running: bool = False
    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def aput_on_shelve(
        self,
        identifier: Identifier,
        value: Any,  # noqa: ANN401
    ) -> str:  # noqa: ANN401
        """Get the shelve for the agent. This is used to get the shelve
        for the agent and all the actors that are spawned from it.
        """

        if hasattr(value, "aget_label"):
            label = await value.aget_label()
        else:
            label = None

        if hasattr(value, "aget_description"):
            description = await value.aget_description()
        else:
            description = None

        drawer = await ashelve(
            instance_id=self.instance_id,
            identifier=identifier,
            resource_id=uuid.uuid4().hex,
            label=label,
            description=description,
            rath=self.rath,
        )

        self.shelve[drawer.id] = value

        return drawer.id

    async def aget_from_shelve(self, key: str) -> Any:  # noqa: ANN401
        """Get a value from the shelve. This is used to get values from the
        shelve for the agent and all the actors that are spawned from it.
        """
        assert key in self.shelve, "Drawer is not in current shelve"
        return self.shelve[key]

    async def acollect(self, key: str) -> None:
        """Collect a value from the shelve. This is used to collect values from the
        shelve for the agent and all the actors that are spawned from it.
        """
        del self.shelve[key]
        await aunshelve(instance_id=self.instance_id, id=key, rath=self.rath)

    async def process(self, message: messages.ToAgentMessage) -> None:
        """Processes a message from the transport. This is used to process
        messages that are sent to the agent from the transport. The agent will
        then send the message to the actors.
        """
        logger.info(f"Agent received {message}")

        if isinstance(message, messages.Init):
            for inquiry in message.inquiries:
                if inquiry.assignation in self.managed_assignments:
                    assignment = self.managed_assignments[inquiry.assignation]
                    actor = self.managed_actors[assignment.actor_id]

                    # Checking status
                    status = await actor.acheck_assignation(assignment.assignation)
                    if status:
                        await self.transport.asend(
                            messages.ProgressEvent(
                                assignation=inquiry.assignation,
                                message="Actor is still running",
                                progress=0,
                            )
                        )
                    else:
                        await self.transport.asend(
                            messages.CriticalEvent(
                                assignation=inquiry.assignation,
                                error="The assignment was not running anymore. But the actor was still managed. This could lead to some race conditions",
                            )
                        )
                else:
                    await self.transport.asend(
                        messages.CriticalEvent(
                            assignation=inquiry.assignation,
                            error="After disconnect actor was no longer managed (probably the app was restarted)",
                        )
                    )

        elif isinstance(message, messages.Assign):
            if message.actor_id in self.managed_actors:
                actor = self.managed_actors[message.actor_id]
                self.managed_assignments[message.assignation] = message
                await actor.apass(message)
            else:
                try:
                    actor = await self.aspawn_actor_from_assign(message)

                    await actor.apass(message)

                except Exception as e:
                    await self.transport.asend(
                        messages.CriticalEvent(
                            assignation=message.assignation,
                            error=f"Not able to create actor through extensions {str(e)}",
                        )
                    )
                    raise e

        elif isinstance(
            message,
            (
                messages.Cancel,
                messages.Step,
                messages.Pause,
                messages.Resume,
            ),
        ):
            if message.assignation in self.managed_assignments:
                assignment = self.managed_assignments[message.assignation]
                actor = self.managed_actors[assignment.actor_id]
                await actor.apass(message)
            else:
                logger.warning(
                    "Received unassignation for a provision that is not running"
                    f"Managed: {self.provision_passport_map} Received: {message.assignation}"
                )
                await self.transport.asend(
                    messages.CriticalEvent(
                        assignation=message.assignation,
                        error="Actors is no longer running and not managed. Probablry there was a restart",
                    )
                )

        elif isinstance(message, messages.Collect):
            for key in message.drawers:
                await self.acollect(key)

        elif isinstance(message, messages.AssignInquiry):
            if message.assignation in self.managed_assignments:
                assignment = self.managed_assignments[message.assignation]
                actor = self.managed_actors[assignment.actor_id]

                # Checking status
                status = await actor.acheck_assignation(assignment.assignation)
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

    async def atear_down(self) -> None:
        """Tears down the agent. This is used to tear down the agent
        and all the actors that are spawned from it.
        """
        logger.info("Tearing down the agent")

        for actor_task in self.managed_actor_tasks.values():
            actor_task.cancel()
        # just stopping the actor, not cancelling the provision..

        for actor_task in self.managed_actor_tasks.values():
            try:
                await actor_task
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

        await self.astop_background()
        await self.transport.adisconnect()

    async def aregister_definitions(self, instance_id: str) -> None:
        """Register all implementations that are handled by extensiosn

        This method is called by the agent when it starts and it is responsible for
        registering the tempaltes that are defined in the extensions.
        """

        self._agent = await aensure_agent(
            instance_id=instance_id,
            name=self.name,
            extensions=[
                extension.get_name()
                for extension in self.extension_registry.agent_extensions.values()
            ],
        )

        for (
            extension_name,
            extension,
        ) in self.extension_registry.agent_extensions.items():
            to_be_created_implementations = await extension.aget_implementations()

            created_implementations = await aset_extension_implementations(
                implementations=to_be_created_implementations,
                run_cleanup=extension.cleanup,
                instance_id=instance_id,
                extension=extension_name,
            )

            for implementation in created_implementations:
                self.interface_implementation_map[implementation.interface] = (
                    implementation
                )
                self.implementation_interface_map[implementation.id] = (
                    implementation.interface
                )

    async def asend(self, actor: "Actor", message: messages.FromAgentMessage) -> None:
        """Sends a message to the actor. This is used for sending messages to the
        agent from the actor. The agent will then send the message to the transport.
        """
        logger.debug(
            f"Agent forwarding {message.id} from actor {actor.__class__.__name__}"
        )
        await self.transport.asend(message)

    async def aregister_state_schemas(self) -> Dict[str, StateSchema]:
        """Register the state schemas for the agent. This will be called when the agent starts"""

        for interface, state_schema_input in self.state_registry.state_schemas.items():
            self._interface_stateschema_map[interface] = await acreate_state_schema(
                state_schema=state_schema_input
            )
            self._interface_stateschema_input_map[interface] = state_schema_input

        return self._interface_stateschema_map

    async def ashrink_state(self, interface: str, state: AnyState) -> Any:  # noqa: ANN401
        """Shrink the state to the schema. This will be called when the agent starts"""
        if interface not in self._interface_stateschema_input_map:
            raise AgentException(f"State {interface} not found in agent {self.name}")

        schema = self._interface_stateschema_input_map[interface]
        structure_registry = self.state_registry.get_registry_for_interface(interface)

        # Shrink the value to the schema
        shrinked_state = await ashrink_state(
            state,
            schema,
            structure_reg=structure_registry,
            shelver=self,
        )
        return shrinked_state

    async def ainit_states(self, hook_return: StartupHookReturns) -> tuple[State, ...]:  # noqa: ANN401
        """Initialize the state of the agent. This will be called when the agent starts"""

        if not self.instance_id:
            raise AgentException("Instance id is not set. The agent is not initialized")

        state_schemas = self.state_registry.state_schemas
        implementations: list[StateImplementationInput] = []

        for interface, startup_value in hook_return.states.items():
            # Set the actual state value
            self.states[interface] = startup_value

            # Set the state schema that is needed to shrink the state
            self._interface_stateschema_input_map[interface] = state_schemas[interface]

            # Shrink the state to the schema
            startup_shrunk_value = await self.ashrink_state(
                interface=interface, state=startup_value
            )

            # Set the shrunk state value
            self._current_shrunk_states[interface] = startup_shrunk_value

            implementations.append(
                StateImplementationInput(
                    interface=interface,
                    stateSchema=state_schemas[interface],
                    initial=startup_shrunk_value,
                )
            )

        states = await aset_agent_states(
            instance_id=self.instance_id,
            implementations=implementations,
        )

        return states

    async def aset_state(self, interface: str, value: AnyState) -> None:  # noqa: ANN401
        """Set the state of the extension. This will be called when the agent starts"""
        from rekuest_next.api.schema import aupdate_state

        if interface not in self.states:
            raise AgentException(f"State {interface} not found in agent {self.name}")

        if interface not in self._current_shrunk_states:
            raise AgentException(
                f"Shrunk State {interface} not found in agent {self.name}"
            )

        if interface not in self._interface_stateschema_input_map:
            raise AgentException(
                f"State Schema {interface} not found in agent {self.name}"
            )

        if not self.instance_id:
            raise AgentException("Instance id is not set. The agent is not initialized")

        old_shrunk_state = self._current_shrunk_states[interface]
        new_shrunk_state = await self.ashrink_state(interface=interface, state=value)

        patch = jsonpatch.make_patch(old_shrunk_state, new_shrunk_state)  # type: ignore

        # Shrink the value to the schema
        state = await aupdate_state(
            interface=interface,
            patches=patch.patch,  # type: ignore
            instance_id=self.instance_id,  # type: ignore
        )

        self._current_shrunk_states[interface] = new_shrunk_state
        self.states[interface] = value

    async def apublish_state(self, state: AnyState) -> None:
        """Publish a state to the agent.  Will forward the state to the transport"""
        interface = self.state_registry.get_interface_for_class(type(state))
        if interface not in self.states:
            raise AgentException(f"State {interface} not found in agent {self.name}")

        await self.aset_state(interface=interface, value=state)

    async def aget_context(self, context: str) -> Any:  # noqa: ANN401
        """Get a context from the agent. This is used to get contexts from the
        agent from the actor."""
        if context not in self.contexts:
            raise AgentException(f"Context {context} not found in agent {self.name}")
        return self.contexts[context]

    async def aget_state(self, interface: str) -> AnyState:
        """Get the state of the extension. This will be called when"""
        if interface not in self.states:
            raise AgentException(f"State {interface} not found in agent {self.name}")
        return self.states[interface]

    async def arun_background(self) -> None:
        """Run the background tasks. This will be called when the agent starts."""
        for name, worker in self.hook_registry.background_worker.items():
            task = asyncio.create_task(
                worker.arun(contexts=self.contexts, states=self.states)
            )
            task.add_done_callback(lambda x: self._background_tasks.pop(name))
            task.add_done_callback(lambda x: print(f"Worker {name} finished"))
            self._background_tasks[name] = task

    async def astop_background(self) -> None:
        """Stop the background tasks. This will be called when the agent stops."""
        for _, task in self._background_tasks.items():
            task.cancel()

        try:
            await asyncio.gather(
                *self._background_tasks.values(), return_exceptions=True
            )
        except asyncio.CancelledError:
            pass

    async def astart(self, instance_id: Optional[str] = None) -> None:
        """Starts the agent. This is used to start the agent and all the actors
        that are spawned from it. The agent will then start the transport and
        start listening for messages from the transport.
        """
        instance_id = instance_id or self.instance_id

        hook_return = await self.hook_registry.arun_startup(instance_id)

        await self.ainit_states(hook_return=hook_return)

        for context_key, context_value in hook_return.contexts.items():
            self.contexts[context_key] = context_value

        await self.arun_background()

        for extension in self.extension_registry.agent_extensions.values():
            await extension.astart(instance_id=instance_id)

        await self.aregister_definitions(instance_id=instance_id)

        self._errorfuture = asyncio.Future()

    async def aspawn_actor_from_assign(self, assign: messages.Assign) -> Actor:
        """Spawns an Actor from a Provision. This function closely mimics the
        spawining protocol within an actor. But maps implementation"""

        if assign.extension not in self.extension_registry.agent_extensions:
            raise ProvisionException(
                f"Extension {assign.extension} not found in agent {self.name}"
            )
        extension = self.extension_registry.agent_extensions[assign.extension]

        actor = await extension.aspawn_actor_for_interface(self, assign.interface)

        self.managed_actors[assign.actor_id] = actor
        self.managed_assignments[assign.assignation] = assign

        return actor

    async def await_errorfuture(self) -> Exception:
        """Waits for the error future to be set. This is used to wait for"""
        if self._errorfuture is None:
            raise AgentException("Error future is not set")

        return await self._errorfuture

    def provide(self, instance_id: Optional[str] = None) -> None:
        """Provides the agent. This starts the agents and
        connected the transport."""
        return unkoil(self.aprovide, instance_id=instance_id)

    async def aloop(self) -> None:
        """Async loop that runs the agent. This is used to run the agent"""
        try:
            self.running = True
            await self.transport.aconnect(self.instance_id)
            async for message in self.transport.areceive():
                await self.process(message)
        except asyncio.CancelledError:
            logger.info(f"Provisioning task cancelled. We are running {self.transport}")
            self.running = False
            await self.atear_down()
            raise
        except Exception as e:
            logger.error(f"Error in agent loop: {str(e)}")
            await self.atear_down()
            raise e

    async def aprovide(self, instance_id: Optional[str] = None) -> None:
        """Provides the agent.

        This starts the agents and connectes to the transport.
        It also starts the agent and starts listening for messages from the transport.

        """
        if instance_id is not None:
            self.instance_id = instance_id

        try:
            logger.info(
                f"Launching provisioning task. We are running {self.instance_id}"
            )
            await self.astart(instance_id=self.instance_id)
            logger.info("Starting to listen for requests")
            await self.aloop()
        except asyncio.CancelledError:
            logger.info("Provisioning task cancelled. We are running")
            await self.atear_down()
            raise

    async def atest(self, instance_id: Optional[str] = None) -> None:
        """Provides the agent.

        This starts the agents and connectes to the transport.
        It also starts the agent and starts listening for messages from the transport.

        """
        if instance_id is not None:
            self.instance_id = instance_id

        provide_task = None

        try:
            logger.info(
                f"Launching provisioning task. We are running {self.instance_id}"
            )
            await self.astart(instance_id=self.instance_id)
            logger.info("Starting to listen for requests")

            provide_task = asyncio.create_task(self.aloop())

            for key, implementation in self.interface_implementation_map.items():
                expandend_implementation = await aget_implementation(
                    instance_id=self.instance_id,
                )

                test_runners: list[Implementation] = []

                try:
                    print(f"Testing implementation for interface {key}")

                    for test_implemtation in test_runners:
                        print("Running test implementation, te")

                        try:
                            task = acall(
                                implementation=test_implemtation,
                                deps={
                                    "implementation": expandend_implementation,
                                },
                            )
                        except Exception as e:
                            print(f"Test implementation failed: {str(e)}")
                            raise e

                except Exception as e:
                    print(
                        f"Testing implementation for interface {key} failed: {str(e)}"
                    )
                    raise e

            provide_task.cancel()

            try:
                await provide_task
            except asyncio.CancelledError:
                pass

            await self.atear_down()

        except asyncio.CancelledError:
            logger.info("Provisioning task cancelled. We are running")
            if provide_task:
                provide_task.cancel()

                try:
                    await provide_task
                except asyncio.CancelledError:
                    pass

            await self.atear_down()

            raise

    async def __aenter__(self) -> Self:
        """Enter the agent context manager. This is used to enter the agent

        context manager and start the agent. The agent will then start the
        transport and start listening for messages from the transport.
        """

        await self.transport.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Exit the agent.

        This method is called when the agent is exited. It is responsible for
        tearing down the agent and all the actors that are spawned from it.

        Args:
            exc_type (Optional[type]): The type of the exception
            exc_val (Optional[Exception]): The exception value
            exc_tb (Optional[type]): The traceback

        """
        await self.atear_down()
        await self.transport.__aexit__(exc_type, exc_val, exc_tb)
