from typing import Any, Dict, List, Union
import uuid
from rekuest_next.api.schema import (
    AssignationFragment,
    ReservationFragment,
    aassign,
    areserve,
    awatch_assignations,
    awatch_reservations,
    aunassign,
    aunreserve,
    BindsInput,
)
import traceback
from rekuest_next.postmans.base import BasePostman
import asyncio
from pydantic import Field
import logging
from .errors import PostmanException
from .vars import current_postman
from rekuest_next.rath import RekuestNextRath

logger = logging.getLogger(__name__)


class GraphQLPostman(BasePostman):
    rath: RekuestNextRath
    instance_id: str
    assignations: Dict[str, AssignationFragment] = Field(default_factory=dict)
    reservations: Dict[str, ReservationFragment] = Field(default_factory=dict)

    _res_update_queues: Dict[str, asyncio.Queue] = {}
    _ass_update_queues: Dict[str, asyncio.Queue] = {}

    _res_update_queue: asyncio.Queue = None
    _ass_update_queue: asyncio.Queue = None

    _watch_resraces_task: asyncio.Task = None
    _watch_assraces_task: asyncio.Task = None
    _watch_reservations_task: asyncio.Task = None
    _watch_assignations_task: asyncio.Task = None

    _watching: bool = None
    _lock: asyncio.Lock = None

    async def aconnect(self):
        await super().aconnect()

        data = {}  # await self.transport.alist_reservations()
        self.reservations = {res.reservation: res for res in data}

        data = {}  # await self.transport.alist_assignations()
        self.assignations = {ass.assignation: ass for ass in data}

    async def areserve(
        self,
        hash: str = None,
        provision: str = None,
        reference: str = "default",
        binds: BindsInput = None,
    ) -> asyncio.Queue:
        async with self._lock:
            if not self._watching:
                await self.start_watching()

        unique_identifier = hash + reference

        self.reservations[unique_identifier] = None
        self._res_update_queues[unique_identifier] = asyncio.Queue()
        try:
            reservation = await areserve(
                instance_id=self.instance_id,
                hash=hash,
                provision=provision,
                reference=reference,
                binds=binds,
                rath=self.rath,
            )
        except Exception as e:
            raise PostmanException("Cannot Reserve") from e

        await self._res_update_queue.put(reservation)
        return self._res_update_queues[unique_identifier]

    async def aunreserve(self, reservation_id: str):
        async with self._lock:
            if not self._watching:
                await self.start_watching()

        try:
            unreservation = await aunreserve(reservation_id)
            self.reservations[unreservation.id] = unreservation
        except Exception as e:
            raise PostmanException("Cannot Unreserve") from e

    async def aassign(
        self,
        reservation: str,
        args: List[Any],
        persist=True,
        log=False,
        reference: str = None,
        parent: Union[AssignationFragment, str] = None,
    ) -> asyncio.Queue:
        async with self._lock:
            if not self._watching:
                await self.start_watching()

        if not reference:
            reference = str(uuid.uuid4())

        self.assignations[reference] = None
        self._ass_update_queues[reference] = asyncio.Queue()
        try:
            assignation = await aassign(
                reservation=reservation, args=args, reference=reference, parent=parent
            )
        except Exception as e:
            raise PostmanException("Cannot Assign") from e
        await self._ass_update_queue.put(assignation)
        return self._ass_update_queues[reference]

    async def aunassign(
        self,
        assignation: str,
    ) -> AssignationFragment:
        async with self._lock:
            if not self._watching:
                await self.start_watching()

        try:
            unassignation = await aunassign(assignation)
        except Exception as e:
            raise PostmanException("Cannot Unassign") from e
        self.assignations[unassignation.id] = unassignation
        return unassignation

    def register_reservation_queue(
        self, node: str, reference: str, queue: asyncio.Queue
    ):
        self._res_update_queues[node + reference] = queue

    def register_assignation_queue(self, ass_id: str, queue: asyncio.Queue):
        self._ass_update_queues[ass_id] = queue

    def unregister_reservation_queue(self, node: str, reference: str):
        del self._res_update_queues[node + reference]

    def unregister_assignation_queue(self, ass_id: str):
        del self._ass_update_queues[ass_id]

    async def watch_reservations(self):
        async for e in awatch_reservations(self.instance_id, rath=self.rath):
            res = e.update or e.create
            await self._res_update_queue.put(res)

    async def watch_assignations(self):
        async for assignation in awatch_assignations(self.instance_id, rath=self.rath):
            ass = assignation.update or assignation.create
            await self._ass_update_queue.put(ass)

    async def watch_resraces(self):
        try:
            while True:
                res: ReservationFragment = await self._res_update_queue.get()

                unique_identifier = res.node.hash + res.reference

                if unique_identifier not in self._res_update_queues:
                    logger.info(
                        "Reservation update for unknown reservation received. Probably"
                        " old stuf"
                    )
                else:
                    if self.reservations[unique_identifier] is None:
                        self.reservations[unique_identifier] = res
                        await self._res_update_queues[unique_identifier].put(res)
                        continue

                    else:
                        if (
                            self.reservations[unique_identifier].updated_at
                            < res.updated_at
                        ):
                            self.reservations[unique_identifier] = res
                            await self._res_update_queues[unique_identifier].put(res)
                        else:
                            logger.info(
                                "Reservation update for reservation {} is older than"
                                " current state. Ignoring".format(unique_identifier)
                            )

                self._res_update_queue.task_done()

        except Exception:
            logger.error("Error in watch_resraces", exc_info=True)

    async def watch_assraces(self):
        try:
            while True:
                ass: AssignationFragment = await self._ass_update_queue.get()
                self._ass_update_queue.task_done()
                logger.info(f"Postman received Assignation {ass}")

                unique_identifier = ass.reference

                if unique_identifier not in self._ass_update_queues:
                    logger.info(
                        "Assignation update for unknown assignation received. Probably"
                        f" old stuf {ass}"
                    )
                    continue

                if self.assignations[unique_identifier] is None:
                    self.assignations[unique_identifier] = ass
                    await self._ass_update_queues[unique_identifier].put(ass)
                    continue

                else:
                    if self.assignations[unique_identifier].updated_at < ass.updated_at:
                        self.assignations[unique_identifier] = ass
                        await self._ass_update_queues[unique_identifier].put(ass)
                    else:
                        logger.info(
                            f"Assignation update for assignation {ass} is older than"
                            " current state. Ignoring"
                        )
                        continue

        except Exception:
            logger.error("Error in watch_resraces", exc_info=True)

    async def start_watching(self):
        logger.info("Starting watching")
        self._res_update_queue = asyncio.Queue()
        self._ass_update_queue = asyncio.Queue()
        self._watch_reservations_task = asyncio.create_task(self.watch_reservations())
        self._watch_reservations_task.add_done_callback(self.log_reservation_fail)
        self._watch_assignations_task = asyncio.create_task(self.watch_assignations())

        self._watch_assignations_task.add_done_callback(self.log_assignation_fail)
        self._watch_resraces_task = asyncio.create_task(self.watch_resraces())
        self._watch_assraces_task = asyncio.create_task(self.watch_assraces())
        self._watching = True

    def log_reservation_fail(self, future):
        """if future.exception():
        exception = future.exception()
        if not isinstance(exception, asyncio.exceptions.CancelledError):
            print(
                str(exception)
                + "\n"
                + "".join(
                    traceback.format_exception(
                        type(exception), exception, exception.__traceback__
                    )
                )
            )"""
        return

    def log_assignation_fail(self, future):
        return

    async def stop_watching(self):
        self._watch_reservations_task.cancel()
        self._watch_assignations_task.cancel()
        self._watch_resraces_task.cancel()
        self._watch_assraces_task.cancel()

        try:
            await asyncio.gather(
                self._watch_reservations_task,
                self._watch_assignations_task,
                self._watch_resraces_task,
                self._watch_assraces_task,
                return_exceptions=True,
            )
        except asyncio.CancelledError:
            pass

        self._watching = False

    async def __aenter__(self):
        self._lock = asyncio.Lock()
        current_postman.set(self)
        return await super().__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._watching:
            await self.stop_watching()
        current_postman.set(None)
        return await super().__aexit__(exc_type, exc_val, exc_tb)

    class Config:
        underscore_attrs_are_private = True
