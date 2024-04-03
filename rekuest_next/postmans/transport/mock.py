from rekuest_next.postmans.transport.base import PostmanTransport
from rekuest_next.messages import (
    Assignation,
    Reservation,
    Unassignation,
    Unreservation,
)
from rekuest_next.api.schema import (
    AssignationStatus,
    ReservationStatus,
    ReserveParamsInput,
)
from typing import Any, Dict, List, Optional, Union
import asyncio
import random
from pydantic import Field
from koil import unkoil
from koil.composition import KoiledModel
from rekuest_next.postmans.transport.protocols.postman_json import (
    ReservePub,
    ReserveSubUpdate,
    AssignPub,
    AssignSubUpdate,
)
import uuid


class MockAutoresolvingPostmanTransport(PostmanTransport):
    """A mock transport for an agent

    Args:
        AgentTransport (_type_): _description_
    """

    assignationState: Dict[str, Assignation] = Field(default_factory=dict)
    unassignationState: Dict[str, Unassignation] = Field(default_factory=dict)
    unreservationState: Dict[str, Unreservation] = Field(default_factory=dict)
    reservationState: Dict[str, Reservation] = Field(default_factory=dict)

    _task: Optional[asyncio.Task] = None

    async def alist_assignations(
        self, exclude: Optional[AssignationStatus] = None
    ) -> List[Assignation]:
        return self.assignationState.values()

    async def alist_reservations(
        self, exclude: Optional[ReservationStatus] = None
    ) -> List[Reservation]:
        return self.reservationState.values()

    async def __aenter__(self):
        self._task = asyncio.create_task(self.aresolve_reservations())

    async def aassign(
        self,
        reservation: str,
        args: List[Any],
        kwargs: Dict[str, Any],
        persist=True,
        log=False,
    ) -> Assignation:
        assignation = Assignation(
            assignation=str(len(self.assignationState) + 1),
            reservation=reservation,
            args=args,
            kwargs=kwargs,
            status=AssignationStatus.PENDING,
        )
        self.assignationState[assignation.assignation] = assignation
        return assignation

    async def areserve(
        self, node: str, params: ReserveParamsInput = None, provision: str = None
    ) -> Reservation:
        reservation = Reservation(
            reservation=str(len(self.reservationState) + 1),
            node=node,
            status=ReservationStatus.ROUTING,
            provision=provision,
        )
        self.reservationState[reservation.reservation] = reservation
        return reservation

    async def aunreserve(self, reservation: str) -> Unreservation:
        self.reservationState[reservation].update(
            Reservation(reservation=reservation, status=ReservationStatus.CANCELLED)
        )
        return Unreservation(reservation=reservation)

    async def aunassign(self, assignation: str) -> Unassignation:
        self.assignationState[assignation].update(
            Assignation(assignation=assignation, status=AssignationStatus.CANCELLED)
        )
        return assignation

    async def aresolve_reservations(self):
        while True:
            await asyncio.sleep(0.1)

            ress = [
                res
                for key, res in self.reservationState.items()
                if res.status == ReservationStatus.ROUTING
            ]
            if ress:
                res = random.choice(ress)
                res.status = ReservationStatus.ACTIVE

                self.reservationState[res.reservation] = res
                await self._abroadcast(res)

            asss = [
                ass
                for key, ass in self.assignationState.items()
                if ass.status == AssignationStatus.PENDING
            ]

            if asss:
                ass = random.choice(asss)
                ass.status = AssignationStatus.RETURNED
                ass.returns = []

                self.assignationState[ass.assignation] = ass
                await self._abroadcast(ass)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._task.cancel()

        try:
            await self._task
        except asyncio.CancelledError:
            pass

    class Config:
        underscore_attrs_are_private = True


class MockPostmanTransport(KoiledModel):
    connected = False
    assignationState: Dict[str, Assignation] = Field(default_factory=dict)
    unassignationState: Dict[str, Unassignation] = Field(default_factory=dict)
    unreservationState: Dict[str, Unreservation] = Field(default_factory=dict)
    reservationState: Dict[str, Reservation] = Field(default_factory=dict)

    _res_update_queues: Dict[str, asyncio.Queue] = {}
    _ass_update_queues: Dict[str, asyncio.Queue] = {}
    _in_queue: asyncio.Queue = None

    async def alist_assignations(
        self, exclude: Optional[AssignationStatus] = None
    ) -> List[Assignation]:
        return []

    async def alist_reservations(
        self, exclude: Optional[ReservationStatus] = None
    ) -> List[Reservation]:
        return []

    async def aconnect(self):
        self._in_queue = asyncio.Queue()
        self.connected = True

    async def __aenter__(self):
        await self.aconnect()
        pass

    async def aassign(
        self,
        reservation: str,
        args: List[Any],
        persist=True,
        log=False,
        reference: str = None,
        parent: str = None,
    ) -> Assignation:
        assert self.connected, "Not connected"

        if not reference:
            reference = str(uuid.uuid4())

        self._ass_update_queues[reference] = asyncio.Queue()

        assignation = AssignPub(
            reservation=reservation,
            args=args,
            parent=parent,
            reference=reference,
        )
        await self._in_queue.put(assignation)
        return self._ass_update_queues[reference]

    async def areserve(
        self,
        node: str,
        params: ReserveParamsInput = None,
        provision: str = None,
        reference: str = "default",
    ) -> Reservation:
        assert self.connected, "Not connected"

        unique_identifier = node + reference

        self.reservationState[unique_identifier] = None
        self._res_update_queues[unique_identifier] = asyncio.Queue()

        reservation = ReservePub(
            node=node,
            reference=reference,
            status=ReservationStatus.ROUTING,
        )

        await self._in_queue.put(reservation)
        return self._res_update_queues[unique_identifier]

    async def aunreserve(self, reservation: str) -> Unreservation:
        assert self.connected, "Not connected"

        unreservation = Unreservation(reservation=reservation)
        await self._in_queue.put(unreservation)
        return unreservation

    async def aunassign(self, assignation: str) -> Unassignation:
        assert self.connected, "Not connected"

        unassignation = Unassignation(assignation=assignation)
        await self._in_queue.put(Unassignation(assignation=assignation))
        return unassignation

    async def adelay(
        self, message: Union[Assignation, Reservation, Unreservation, Unassignation]
    ):
        if isinstance(message, ReserveSubUpdate):
            unique_identifier = message.node + message.reference
            return await self._res_update_queues[unique_identifier].put(message)

        if isinstance(message, AssignSubUpdate):
            unique_identifier = message.reference
            return await self._ass_update_queues[unique_identifier].put(message)

        raise NotImplementedError()

    async def areceive(self, timeout=None):
        if timeout:
            return await asyncio.wait_for(self._in_queue.get(), timeout)
        return await self._in_queue.get()

    def delay(
        self, message: Union[Assignation, Reservation, Unreservation, Unassignation]
    ):
        return unkoil(self.adelay, message)

    def receive(self, *args, **kwargs):
        return unkoil(self.areceive, *args, **kwargs)

    class Config:
        underscore_attrs_are_private = True
        arbitrary_types_allowed = True
