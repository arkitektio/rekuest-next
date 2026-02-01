"""The base class for all actors."""

import asyncio
import contextlib
import logging
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Self,
    Tuple,
)
import uuid
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

from rekuest_next.actors.errors import UnknownMessageError
from rekuest_next.agents.errors import StateRequirementsNotMet
from rekuest_next.actors.types import Agent
from rekuest_next import messages
from rekuest_next.definition.define import DefinitionInput
from rekuest_next.protocols import AnyContext, AnyState
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.structures.default import get_default_structure_registry
from rekuest_next.actors.sync import SyncGroup
from rekuest_next.state.lock import acquired_locks

logger = logging.getLogger(__name__)


class Passport(BaseModel):
    """The passport of the actor. This is used to identify the actor and"""

    instance_id: str
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class Actor(BaseModel):
    """The base class for all actors.

    Actors are the main building blocks of the system and are used to
    perform actions that they receive from the agent. They are responsible for
    processing the actions and sending the results back to the agent.

    Actors are long running processes that are managed by the agent.

    """

    agent: Agent = Field(
        description="The agent that is managing the actor. This is used to send messages to the agent"
    )
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="The id of the actor")
    model_config = ConfigDict(arbitrary_types_allowed=True)
    running_assignments: Dict[str, messages.Assign] = Field(default_factory=dict)
    locks: Optional[Tuple[str, ...]] = Field(
        default=None,
        description="The sync keys this actor requires. Locks will be acquired before running.",
    )
    sync: SyncGroup = Field(
        default_factory=SyncGroup,
        description="The sync group to use for this actor. This is used to synchronize access to the actor.",
    )

    _running_asyncio_tasks: Dict[str, asyncio.Task[None]] = PrivateAttr(default_factory=lambda: {})
    _break_futures: Dict[str, asyncio.Future[bool]] = PrivateAttr(default_factory=lambda: {})

    @model_validator(mode="before")
    def validate_sync(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """A default syncgroup will be created if none is set"""
        if values.get("sync") is None:
            values["sync"] = SyncGroup()
        return values

    @contextlib.asynccontextmanager
    async def sync_context(self: Self, assignation_id: str, interface: str):
        """Context manager that acquires sync key locks and the regular sync group.

        This should be used instead of `async with self.sync:` when sync keys are defined.
        It first acquires all sync key locks, then the regular sync group.

        Args:
            assignation_id: The ID of the assignation.
            interface: The interface name for this actor.

        Yields:
            None after all locks are acquired.
        """
        from rekuest_next.actors.sync import SyncKeyGroup

        # Create SyncKeyGroup if locks are defined
        sync_key_group = None
        if self.locks:
            locks = self.agent.get_locks_for_keys(self.locks)
            if locks:
                sync_key_group = SyncKeyGroup(
                    locks=locks,
                    assignation_id=assignation_id,
                    interface=interface,
                )

        try:
            # Acquire sync key locks first
            if sync_key_group:
                await sync_key_group.acquire()

            # Then acquire the regular sync group

            async with self.sync:
                with acquired_locks(*(self.locks or [])):
                    yield
        finally:
            # Release sync key locks
            if sync_key_group:
                await sync_key_group.release()

    async def on_resume(self: Self, resume: messages.Resume) -> None:
        """A function that is called once the actor is resumed from a paused state.
        This can be used to re-initialize the actor after a pause.

        Args:
            resume (Resume): The resume message containing the information about the
                actor that was resumed.
        """
        if resume.assignation in self._break_futures:
            self._break_futures[resume.assignation].set_result(True)
            del self._break_futures[resume.assignation]
        else:
            logger.warning(
                f"Actor {self.id} was resumed but no break future was found for {resume.assignation}"
            )

    async def asend(
        self: Self,
        message: messages.FromAgentMessage,
    ) -> None:
        """A function to send a message to the agent. This is used to send messages
        to the agent from the actor.

        Args:
            transport (AssignTransport): The transport to use to send the message
            message (ToAgentMessage): The message to send
        """
        await self.agent.asend(self, message=message)

    async def on_pause(self: Self, pause: messages.Pause) -> None:
        """A function that is called once the actor is paused. This can be used to
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

    async def on_step(self: Self, step: messages.Step) -> None:
        """A function that is called once the actor is asked to do a step,
        normally this should handle a resume following an immediate resume.

        Args:
            pause (Pause): The pause message containing the information about the
                actor that was stepped.
        """
        return None

    async def on_assign(
        self: Self,
        assignment: messages.Assign,
    ) -> None:
        """A function that is called once the actor is assigned a task. This is used to
        process the task and send the results back to the agent.

        Args:
            assignment (messages.Assign): The assignment message containing the information about the
             assignment.
            collector (AssignationCollector): A collector that is used to collect the results of the assignment.
            transport (AssignTransport): A transport that is used to send the results of the assignment back to the agent (keeps ference to the original assignment)

        Raises:
            NotImplementedError: Needs to be overwritten in Actor subclass. Never use this class directly
        """
        raise NotImplementedError(
            "Needs to be owerwritten in Actor Subclass. Never use this class directly"
        )

    async def apass(self: Self, message: messages.ToAgentMessage) -> None:
        """A function that is called once the actor is passed a message. This is used to
        process the message and send the results back to the agent.

        Args:
            self (Self): A reference to the actor instance.
            message (messages.FromAgentMessage):   The message to process.
        """
        await self.aprocess(message)

    async def acancel(self: Self) -> None:
        """A function to cancel the actor. This is used to cancel the actor and
        stop listening for messages from the agent.
        """
        # Cancel Mnaged actors
        logger.info(f"Cancelling Actor {self.id}")

        [i.cancel() for i in self._running_asyncio_tasks.values()]

        for key, task in self._running_asyncio_tasks.items():
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"Task {key} was cancelled through applicaction. Setting Critical")
                await self.agent.asend(
                    self,
                    message=messages.CriticalEvent(
                        assignation=key,
                        error="Cancelled trhough application (this is not nice from the application and will be regarded as an error)",
                    ),
                )

    async def abreak(self: Self, assignation_id: str) -> bool:
        """A function to break the actor. This is used to instruct the actor to
        stop processing the assignment at the current time
        """
        if assignation_id in self._break_futures:
            await self._break_futures[assignation_id]
            return True
        else:
            logger.warning(
                f"Currently no break future for {assignation_id} was found. Wasn't paused"
            )
            return False

    def assign_task_done(self: Self, task: asyncio.Task[None]) -> None:
        """A function that is called once the assignment task is done. This can be
        used in debugging to check if the task was cancelled or if it was done successfully.

        Args:
            task (asyncio.Task): The task that was done.
        """

        logger.info(f"Assign task is done: {task}")
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Assign task {task} failed with exception {e}", exc_info=True)
        pass

    async def acheck_assignation(self: Self, assignation_id: str) -> bool:
        """A function to check if the assignment is still running. This is used to
        check if the assignment is still running and if it is still valid.

        Args:
            id (str): The id of the assignment to check.
        Returns:
            bool: True if the assignment is still running, False otherwise.
        """
        if assignation_id in self._running_asyncio_tasks:
            return True
        return False

    async def aprocess(self: Self, message: messages.ToAgentMessage) -> None:
        """A function to process the message. This is used to process the message
        and send the results back to the agent.


        Args:
            message (messages.ToAgentMessage): The message to process.
        """

        logger.info(f"Actor for {self.id}: Received {message}")

        if isinstance(message, messages.Assign):
            task = asyncio.create_task(
                self.on_assign(
                    message,
                )
            )

            task.add_done_callback(self.assign_task_done)
            self._running_asyncio_tasks[message.assignation] = task

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

                        del self._running_asyncio_tasks[message.assignation]
                        await self.agent.asend(
                            self,
                            message=messages.CancelledEvent(assignation=message.assignation),
                        )

                else:
                    logger.warning("Race Condition: Task was already done before cancellation")
                    await self.agent.asend(
                        self,
                        message=messages.CancelledEvent(assignation=message.assignation),
                    )

            else:
                logger.error(
                    f"Actor for {self}: Received unassignment for unknown assignation {message.id}"
                )
        else:
            raise UnknownMessageError(f"{message}")

    async def apublish_state(self: Self, state: AnyState) -> None:
        """A function to publish the state of the actor. This is used to publish the
        state of the actor to the agent.

        Args:
            state (AnyState): The state to publish.
        """
        await self.agent.apublish_state(state)


class SerializingActor(Actor):
    """A serializing actor is an actor that will
    serialize and deserialize the arguments and return values
    of the assignments it receives.

    """

    definition: DefinitionInput = Field(
        description="The definition of the actor, describing what arguents and return values it provides"
    )
    structure_registry: StructureRegistry = Field(
        default=get_default_structure_registry(),
        description="The structure regsistry to use for this actor",
    )
    expand_inputs: bool = Field(
        default=True,
        description="Whether to expand the inputs of the actor. Can overwrite the default behaviour of the actor to expand the inputs with the structure registry.",
    )
    shrink_outputs: bool = Field(
        default=True,
        description="Whether to shrink the outputs of the actor. Can overwrite the default behaviour of the actor to shrink the outputs with the structure registry.",
    )
    state_variables: Dict[str, Any] = Field(
        default_factory=dict, description="The state variables of the actor"
    )
    context_variables: Dict[str, Any] = Field(default_factory=dict)

    async def aget_locals(
        self: Self,
    ) -> Tuple[Mapping[str, AnyContext], Mapping[str, AnyState]]:
        """A function to for locals"""

        state_kwargs: Mapping[str, AnyContext | AnyState] = {}
        context_kwargs: Mapping[str, AnyContext] = {}

        for key, interface in self.context_variables.items():
            try:
                context_kwargs[key] = await self.agent.aget_context(interface)
            except KeyError as e:
                raise StateRequirementsNotMet(f"State requirements not met: {e}") from e

        for key, interface in self.state_variables.items():
            try:
                state_kwargs[key] = await self.agent.aget_state(interface)
            except KeyError as e:
                raise StateRequirementsNotMet(f"State requirements not met: {e}") from e

        return context_kwargs, state_kwargs

    async def async_locals(self: Self, state_params: Mapping[str, AnyState]) -> None:
        """A function to again sync the state of the actor with the state params
        Args:
            state_params (Mapping[str, AnyState]): The state params to sync with
        """
        for key, _ in self.state_variables.items():
            if key in state_params:
                state = state_params[key]
                await self.agent.apublish_state(
                    state,
                )
            else:
                logger.warning(f"State {key} not found in state params")


Actor.model_rebuild()
SerializingActor.model_rebuild()
