from random import random
from typing import (
    Awaitable,
    Callable,
    Coroutine,
    Optional,
    Union,
    TypeVar,
    runtime_checkable,
    Protocol,
    Any,
    Dict,
    List,
    AsyncIterator,
)
import uuid
from pydantic import Field
from rekuest_next.messages import AssignationEvent, ProvisionEvent
from rekuest_next.structures.default import get_default_structure_registry
from koil.composition import KoiledModel
from koil.types import ContextBool
import uuid
import asyncio
import logging
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.api.schema import (
    BindsInput,
    DefinitionFragment,
    ReservationFragment,
    TemplateFragment,
    afind,
)
from .errors import (
    AssignException,
    IncorrectReserveState,
    PostmanException,
    RecoverableAssignException,
)
from rekuest_next.actors.base import Actor, SerializingActor
from rekuest_next.agents.transport.base import AgentTransport
from .base import BasePostman
from rekuest_next.actors.types import (
    Passport,
    Assignment,
    Unassignment,
    AssignmentUpdate,
)
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ContractStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


@runtime_checkable
class ContractStateHook(Protocol):
    async def __call__(
        self, state: ContractStatus = None, reference: str = None
    ) -> None: ...


@runtime_checkable
class RPCContract(Protocol):
    async def __aenter__(self: Any) -> Any: ...

    async def __aexit__(self, exc_type, exc, tb): ...

    async def change_state(self, state: ContractStatus): ...

    async def aassign(
        self,
        kwargs: Dict[str, Any],
        parent: Optional[Assignment] = None,
        reference: Optional[str] = None,
        assign_timeout: Optional[float] = None,
    ) -> Dict[str, Any]: ...

    async def aassign_retry(
        self,
        kwargs: Dict[str, Any],
        parent: Optional[Assignment] = None,
        reference: Optional[str] = None,
        assign_timeout: Optional[float] = None,
        retry: Optional[int] = 0,
    ) -> Dict[str, Any]: ...

    async def astream(
        self,
        kwargs: Dict[str, Any],
        parent: Optional[Assignment] = None,
        reference: Optional[str] = None,
        yield_timeout: Optional[float] = None,
    ) -> AsyncIterator[List[Any]]: ...

    async def astream_retry(
        self,
        kwargs: Dict[str, Any],
        parent: Optional[Assignment] = None,
        reference: Optional[str] = None,
        yield_timeout: Optional[float] = None,
        retry: Optional[int] = 0,
    ) -> Dict[str, Any]: ...


class RPCContractBase(KoiledModel):
    max_retries: int = 3
    retry_delay_ms: float = 1000
    reference: Optional[str]
    active: ContextBool = Field(default=False)
    state: ContractStatus = Field(default=ContractStatus.INACTIVE)
    state_hook: Optional[ContractStateHook] = None
    timeout_is_recoverable: bool = True

    async def aenter(self):
        raise NotImplementedError("Should be implemented by subclass")

    async def aexit(self):
        raise NotImplementedError("Should be implemented by subclass")

    async def change_state(self, state: ContractStatus):
        self.state = state
        if self.state_hook:
            await self.state_hook(state=state, reference=self.reference)

    async def aassign(
        self,
        kwargs: Dict[str, Any],
        parent: Optional[Assignment] = None,
        reference: Optional[str] = None,
        assign_timeout: Optional[int] = None,
    ):
        raise NotImplementedError("Should be implemented by subclass")

    async def astream(
        self,
        kwargs: Dict[str, Any],
        parent: Optional[Assignment] = None,
        reference: Optional[str] = None,
        yield_timeout: Optional[int] = None,
    ):
        raise NotImplementedError("Should be implemented by subclass")

    async def astream_retry(
        self,
        kwargs: Dict[str, Any],
        parent: Optional[Assignment] = None,
        yield_timeout: Optional[int] = None,
        retry: Optional[int] = 0,
        reference: Optional[str] = None,
        retry_delay_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        try:
            async for i in self.astream(
                kwargs={**kwargs},
                parent=parent,
                reference=reference,
                yield_timeout=yield_timeout,
            ):
                yield i
        except RecoverableAssignException as e:
            logger.warning(f"Stream failed with {e}")
            if retry < self.max_retries:
                await asyncio.sleep((retry_delay_ms or self.retry_delay_ms) * 0.001)
                async for i in self.astream_retry(
                    kwargs=kwargs,
                    parent=parent,
                    reference=reference,
                    yield_timeout=yield_timeout,
                    retry=retry + 1,
                    retry_delay_ms=retry_delay_ms,
                ):
                    yield i
            else:
                raise e

    async def aassign_retry(
        self,
        kwargs: Dict[str, Any],
        parent: Optional[Assignment] = None,
        assign_timeout: Optional[int] = None,
        retry: Optional[int] = 0,
        reference: Optional[str] = None,
        retry_delay_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        try:
            return await self.aassign(
                kwargs={**kwargs},
                parent=parent,
                reference=reference,
                assign_timeout=assign_timeout,
            )
        except RecoverableAssignException as e:
            logger.warning(f"Assign failed with {e}")
            if retry < self.max_retries:
                logger.info(f"Retrying in {retry_delay_ms or self.retry_delay_ms}ms")
                await asyncio.sleep((retry_delay_ms or self.retry_delay_ms) * 0.001)
                return await self.aassign_retry(
                    kwargs=kwargs,
                    parent=parent,
                    reference=reference,
                    assign_timeout=assign_timeout,
                    retry=retry + 1,
                    retry_delay_ms=retry_delay_ms,
                )
            else:
                raise e

    async def __aenter__(self: T) -> T:
        await self.aenter()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.aexit()


class actoruse(RPCContractBase):
    template: TemplateFragment
    supervisor: Actor = Field(repr=False, exclude=True)
    reference: Optional[str]
    "The governing actor"
    assign_timeout: Optional[float] = 36000
    yield_timeout: Optional[float] = 2000

    _transport: AgentTransport = None
    _actor: SerializingActor
    _enter_future: asyncio.Future = None
    _exit_future: asyncio.Future = None
    _updates_queue: asyncio.Queue[Union[AssignationEvent, ProvisionEvent]] = None
    _updates_watcher: asyncio.Task = None
    _assign_queues = {}

    async def aassign(
        self,
        kwargs: Dict[str, Any],
        parent: Optional[Assignment] = None,
        assign_timeout: Optional[float] = None,
        reference: Optional[str] = None,
    ) -> Dict[str, Any]:
        assignment = Assignment(
            assignation=parent.assignation if parent else None,
            parent=parent.id if parent else None,
            args=serialize_inputs(self._actor.definition, kwargs),
            status=AssignationStatus.ASSIGNED,
            user=parent.user if parent else None,
            reference=reference,
        )

        _ass_queue = asyncio.Queue[AssignmentUpdate]()
        self._assign_queues[assignment.id] = _ass_queue

        await self._actor.apass(assignment)
        try:
            while True:  # Waiting for assignation
                logger.info("Waiting for update")
                ass = await asyncio.wait_for(
                    _ass_queue.get(), timeout=assign_timeout or self.assign_timeout
                )
                logger.info(f"Local Assign Context: {ass}")
                if ass.status == AssignationStatus.RETURNED:
                    return deserialize_outputs(self._actor.definition, ass.returns)

                if ass.status in [AssignationStatus.ERROR]:
                    raise RecoverableAssignException(
                        f"Recoverable Exception: {ass.message}"
                    )

                if ass.status in [AssignationStatus.CRITICAL]:
                    raise AssignException(f"Critical error: {ass.message}")

                if ass.status in [AssignationStatus.CANCELLED]:
                    raise AssignException("Was cancelled from the outside")

                _ass_queue.task_done()
        except asyncio.CancelledError as e:
            await self._actor.apass(
                Unassignation(
                    assignation=id,
                )
            )

            ass = await asyncio.wait_for(_ass_queue.get(), timeout=2)
            if ass.status == AssignationStatus.CANCELING:
                logger.info("Wonderfully cancelled that assignation!")
                raise e

            raise AssignException(f"Critical error: {ass}")

        except asyncio.TimeoutError as e:
            exc_class = (
                RecoverableAssignException
                if self.timeout_is_recoverable
                else AssignException
            )

            raise exc_class("Timeout error for assignation") from e

        except Exception as e:
            logger.error("Error in Assignation", exc_info=True)
            raise e

    async def on_actor_log(self, *args, **kwargs):
        logger.info(f"ActorLog: {args} {kwargs}")

    async def on_assign_log(self, *args, **kwargs):
        logger.info(f"AssingLog: {args} {kwargs}")

    async def on_actor_change(self, passport: Passport, status, **kwargs):
        # passport is irellevant because we only every manage one actor
        if status == ProvisionStatus.ACTIVE:
            await self.change_state(ContractStatus.ACTIVE)
            if self._enter_future and not self._enter_future.done():
                self._enter_future.set_result(True)

        else:
            await self.change_state(ContractStatus.INACTIVE)
            if self._enter_future and not self._enter_future.done():
                self._enter_future.set_exception(Exception("Error on provision"))

    async def astream(
        self,
        kwargs: Dict[str, Any],
        parent: Optional[Assignment] = None,
        yield_timeout: Optional[float] = None,
        reference: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        inputs = serialize_inputs(self._actor.definition, kwargs)
        assignment = Assignment(
            assignation=parent.assignation if parent else None,
            parent=parent.id if parent else None,
            args=inputs,
            status=AssignationStatus.ASSIGNED,
            user=parent.user if parent else None,
            reference=reference,
        )

        _ass_queue = asyncio.Queue[AssignmentUpdate]()
        self._assign_queues[assignment.id] = _ass_queue

        await self._actor.apass(assignment)

        try:
            while True:  # Waiting for assignation
                ass = await asyncio.wait_for(
                    _ass_queue.get(), timeout=yield_timeout or self.yield_timeout
                )
                logger.info(f"Local Stream Context: {ass}")
                if ass.status == AssignationStatus.YIELD:
                    yield deserialize_outputs(self._actor.definition, ass.returns)

                if ass.status == AssignationStatus.DONE:
                    return

                if ass.status in [AssignationStatus.CRITICAL, AssignationStatus.ERROR]:
                    raise AssignException(f"Critical error: {ass.message}")

                _ass_queue.task_done()

        except asyncio.CancelledError as e:
            await self._actor.apass(
                Unassignment(assignation=assignment.id, id=assignment.id)
            )

            ass = await asyncio.wait_for(_ass_queue.get(), timeout=2)
            if ass.status == AssignationStatus.CANCELING:
                logger.info("Wonderfully cancelled that assignation!")
                raise e

            raise e

        except asyncio.TimeoutError as e:
            exc_class = (
                RecoverableAssignException
                if self.timeout_is_recoverable
                else AssignException
            )

            raise exc_class("Timeout error for assignation") from e

        except Exception as e:
            logger.error(exc_info=True)
            raise e

    async def on_assign_change(
        self,
        assignment: Assignment,
        status=None,
        returns=None,
        progress=None,
        message=None,
    ):
        await self._assign_queues[assignment.id].put(
            AssignmentUpdate(
                assignment=assignment.id,
                status=status,
                returns=returns,
                progress=progress,
                message=message,
            )
        )

        return

    async def aenter(self):
        self._enter_future = asyncio.Future()
        self._updates_queue = asyncio.Queue[AssignationChangedMessage]()

        self._actor = await self.supervisor.aspawn_actor(
            self.template,
            on_actor_log=self.on_actor_log,
            on_actor_change=self.on_actor_change,
            on_assign_change=self.on_assign_change,
            on_assign_log=self.on_assign_log,
        )

        await self._actor.arun()
        await self._enter_future

    async def aexit(self):
        if self._actor:
            await self._actor.acancel()

    class Config:
        arbitrary_types_allowed = True


class arkiuse(RPCContractBase):
    hash: Optional[str] = None
    provision: Optional[str] = None
    reference: str = "default"
    binds: Optional[BindsInput] = None
    postman: BasePostman = Field(repr=False)
    reserve_timeout: Optional[int] = 100000
    assign_timeout: Optional[int] = 100000
    yield_timeout: Optional[int] = 100000
    auto_unreserve: bool = False

    _reservation: ReservationFragment = None
    _enter_future: asyncio.Future = None
    _exit_future: asyncio.Future = None
    _updates_queue: asyncio.Queue = None
    _updates_watcher: asyncio.Task = None
    _definition: Optional[DefinitionFragment] = None

    async def aassign(
        self,
        kwargs: Dict[str, Any],
        parent: Optional[Assignment] = None,
        assign_timeout: Optional[int] = None,
        reference: Optional[str] = None,
    ) -> Dict[str, Any]:
        assert self._reservation, "We never entered the context manager"
        if self.state != ContractStatus.ACTIVE:
            raise IncorrectReserveState(
                f"Contract is not active at the moment: {self.state}"
            )

        inputs = serialize_inputs(self._definition, kwargs)

        try:
            _ass_queue = await self.postman.aassign(
                self._reservation.id,
                inputs,
                parent=parent.assignation if parent else None,
                reference=reference,
            )
        except PostmanException as e:
            raise AssignException("Cannot do initial assignment") from e

        ass = None
        try:
            while True:  # Waiting for assignation
                ass = await asyncio.wait_for(
                    _ass_queue.get(), timeout=assign_timeout or self.assign_timeout
                )
                logger.info(f"Assign Context: {ass}")
                if ass.status == AssignationStatus.RETURNED:
                    return deserialize_outputs(self._definition, ass.returns)

                if ass.status in [AssignationStatus.ERROR]:
                    raise RecoverableAssignException(
                        f"Recoverable Exception: {ass.statusmessage}"
                    )

                if ass.status in [AssignationStatus.CRITICAL]:
                    raise AssignException(f"Critical error: {ass.statusmessage}")

                if ass.status in [AssignationStatus.CANCELLED]:
                    raise AssignException("Was cancelled from the outside")

        except asyncio.CancelledError as e:
            if ass:
                await self.postman.aunassign(ass.id)

                ass = await asyncio.wait_for(_ass_queue.get(), timeout=2)
                if ass.status == AssignationStatus.CANCELING:
                    logger.info("Wonderfully cancelled that assignation!")
                    raise e

                raise PostmanException(
                    f"Unexpected Arkitekt repsonse while trying to cancel exception: {ass}"
                )

        except asyncio.TimeoutError as e:
            if ass:
                logger.warning(
                    f"Cancelling this assignation but not wait for request {ass}"
                )
                await self.postman.aunassign(ass.id)

            exc_class = (
                RecoverableAssignException
                if self.timeout_is_recoverable
                else AssignException
            )

            raise exc_class("Timeout error for assignation") from e

    async def astream(
        self,
        kwargs: Dict[str, Any],
        parent: Optional[Assignment] = None,
        yield_timeout: Optional[int] = None,
        reference: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        assert self._reservation, "We never entered the context manager"
        if self.state != ContractStatus.ACTIVE:
            raise IncorrectReserveState(
                f"Contract is not active at the moment: {self.state}"
            )

        try:
            _ass_queue = await self.postman.aassign(
                self._reservation.id,
                serialize_inputs(self._definition, kwargs),
                parent=parent.assignation if parent else None,
                reference=reference,
            )
        except PostmanException as e:
            raise AssignException("Cannot do initial assignment") from e
        ass = None

        try:
            while True:  # Waiting for assignation
                ass = await asyncio.wait_for(
                    _ass_queue.get(), timeout=yield_timeout or self.yield_timeout
                )
                logger.info(f"Stream Context: {ass}")
                if ass.status == AssignationStatus.YIELD:
                    yield deserialize_outputs(self._definition, ass.returns)

                if ass.status in [AssignationStatus.DONE]:
                    return

                if ass.status in [AssignationStatus.ERROR]:
                    raise RecoverableAssignException(
                        f"Recoverable Exception: {ass.statusmessage}"
                    )

                if ass.status in [AssignationStatus.CRITICAL]:
                    raise AssignException(f"Critical error: {ass.statusmessage}")

                if ass.status in [AssignationStatus.CANCELLED]:
                    raise AssignException("Was cancelled from the outside")

        except asyncio.CancelledError as e:
            if ass:
                logger.warning(f"Cancelling this assignation {ass}")
                await self.postman.aunassign(ass.id)

                ass = await asyncio.wait_for(_ass_queue.get(), timeout=2)
                if ass.status == AssignationStatus.CANCELING:
                    logger.info("Wonderfully cancelled that assignation!")
                    raise e

                raise PostmanException(
                    f"Unexpected Arkitekt repsonse while trying to cancel exception: {ass}"
                )

        except asyncio.TimeoutError as e:
            if ass:
                logger.warning(
                    f"Cancelling this assignation but not wait for request {ass}"
                )
                await self.postman.aunassign(ass.id)

            exc_class = (
                RecoverableAssignException
                if self.timeout_is_recoverable
                else AssignException
            )

            raise exc_class("Timeout error for assignation") from e

    async def watch_updates(self):
        logger.info("Waiting for updates")
        try:
            while True:
                self._reservation = await self._updates_queue.get()
                logger.info(f"Updated Reservation {self._reservation}")
                if self._reservation.status == ReservationStatus.ROUTING:
                    logger.info("Reservation is routing")

                elif self._reservation.status == ReservationStatus.ACTIVE:
                    if self._enter_future and not self._enter_future.done():
                        logger.info("Entering future")
                        self._enter_future.set_result(True)

                    await self.change_state(ContractStatus.ACTIVE)

                elif self._reservation.status == ReservationStatus.DISCONNECT:
                    if self._enter_future and not self._enter_future.done():
                        logger.info("Entering future")
                        self._enter_future.set_result(True)

                    await self.change_state(ContractStatus.INACTIVE)

                else:
                    logger.error(
                        f"Currently unhandled status {self._reservation.status}"
                    )
                    if self._enter_future and not self._enter_future.done():
                        self._enter_future.set_exception(True)

                    await self.change_state(ContractStatus.INACTIVE)

        except asyncio.CancelledError:
            pass

    async def aenter(self):
        logger.info(f"Trying to reserve {self.hash}")

        self._enter_future = asyncio.Future()
        self._definition = await afind(hash=self.hash)
        self._updates_queue = await self.postman.areserve(
            hash=self.hash,
            params=self.params,
            provision=self.provision,
            reference=self.reference,
            binds=self.binds,
        )
        try:
            self._updates_watcher = asyncio.create_task(self.watch_updates())
            await asyncio.wait_for(
                self._enter_future, self.reserve_timeout
            )  # Waiting to enter

        except asyncio.TimeoutError:
            logger.warning("Reservation timeout")
            self._updates_watcher.cancel()

            try:
                await self._updates_watcher
            except asyncio.CancelledError:
                pass

            raise

        return self

    async def aexit(self):
        self.active = False

        if self._reservation:
            if self.auto_unreserve:
                logger.info(f"Unreserving {self.hash}")
                await self.postman.aunreserve(self._reservation.id)

        if self._updates_watcher:
            self._updates_watcher.cancel()

            try:
                await self._updates_watcher
            except asyncio.CancelledError:
                pass

    class Config:
        arbitrary_types_allowed = True


class mockuse(RPCContract):
    returns: tuple = (1,)
    streamevents: int = 3
    assign_sleep: float = Field(default_factory=random)
    reserve_sleep: float = Field(default_factory=random)
    unreserve_sleep: float = Field(default_factory=random)
    stream_sleep: float = Field(default_factory=random)

    async def aenter(self):
        await asyncio.sleep(self.reserve_sleep)
        self.active = True
        return self

    async def aexit(self):
        self.active = False
        await asyncio.sleep(self.unreserve_sleep)

    async def aassign(
        self,
        *args,
        structure_registry=None,
        alog,
        **kwargs,
    ):
        assert self.active, "We never entered the contract"
        if alog:
            await alog(
                Assignation(assignation=str(uuid.uuid4())),
                AssignationLogLevel.INFO,
                "Mock assignation",
            )
        await asyncio.sleep(self.assign_sleep)
        return self.returns

    async def astream(
        self,
        *args,
        structure_registry=None,
        alog,
        **kwargs,
    ):
        assert self.active, "We never entered the contract"
        if alog:
            await alog(
                Assignation(assignation=str(uuid.uuid4())),
                AssignationLogLevel.INFO,
                "Mock assignation",
            )
        for i in range(self.streamevents):
            await asyncio.sleep(self.stream_sleep)
            yield self.returns

    class Config:
        arbitrary_types_allowed = True


class serializingarkiuse(arkiuse):
    structure_registry: StructureRegistry = Field(
        default_factory=get_default_structure_registry, repr=False
    )

    async def aassign(
        self,
        *args,
        parent: Optional[Assignment] = None,
        assign_timeout: Optional[int] = None,
        reference: Optional[str] = None,
        **kwargs,
    ) -> Coroutine[Any, Any, Dict[str, Any]]:
        shrinked_kwargs = await shrink_inputs(
            self._definition, args, kwargs, self.structure_registry
        )

        unshrunk = await super().aassign(
            shrinked_kwargs, parent, assign_timeout, reference
        )

        return await expand_outputs(self._definition, unshrunk, self.structure_registry)
