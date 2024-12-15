from typing import AsyncGenerator, Dict
from rekuest_next.api.schema import (
    AssignationEvent,
    Assignation,
    aassign,
    awatch_assignations,
    acancel,
    aunreserve,
    AssignInput,
)
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
    assignations: Dict[str, Assignation] = Field(default_factory=dict)

    _ass_update_queues: Dict[str, asyncio.Queue] = {}

    _ass_update_queue: asyncio.Queue = None

    _watch_assraces_task: asyncio.Task = None
    _watch_assignations_task: asyncio.Task = None

    _watching: bool = None
    _lock: asyncio.Lock = None

    async def aconnect(self):
        await super().aconnect()
        data = {}  # await self.transport.alist_assignations()
        self.assignations = {ass.assignation: ass for ass in data}

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
        self, assign: AssignInput
    ) -> AsyncGenerator[AssignationEvent, None]:
        async with self._lock:
            if not self._watching:
                await self.start_watching()

        try:
            assignation = await aassign(**assign.model_dump())
        except Exception as e:
            raise PostmanException("Cannot Assign") from e

        self._ass_update_queues[assign.reference] = asyncio.Queue()
        queue = self._ass_update_queues[assign.reference]

        try:
            while True:
                signal = await queue.get()
                yield signal
                queue.task_done()

        except asyncio.CancelledError as e:
            unassignation = await acancel(assignation=assignation.id)
            del self._ass_update_queues[assign.reference]
            raise e

    def register_assignation_queue(self, ass_id: str, queue: asyncio.Queue):
        self._ass_update_queues[ass_id] = queue

    def unregister_assignation_queue(self, ass_id: str):
        del self._ass_update_queues[ass_id]

    async def watch_assignations(self):
        try:
            async for assignation in awatch_assignations(
                self.instance_id, rath=self.rath
            ):
                if assignation.event:
                    reference = assignation.event.reference
                    await self._ass_update_queues[reference].put(assignation.event)
                if assignation.create:
                    if assignation.create.reference not in self._ass_update_queues:
                        logger.critical("RACE CONDITION EXPERIENCED")

        except Exception as e:
            logger.error("Watching Assignations failed", exc_info=True)
            raise e

    async def watch_assraces(self):
        try:
            while True:
                ass: AssignationEvent = await self._ass_update_queue.get()
                self._ass_update_queue.task_done()
                logger.info(f"Postman received Assignation {ass}")

                unique_identifier = ass.reference

                await self._ass_update_queues[unique_identifier].put(ass)

        except Exception:
            logger.error("Error in watch_resraces", exc_info=True)

    async def start_watching(self):
        logger.info("Starting watching")
        self._ass_update_queue = asyncio.Queue()
        self._watch_assignations_task = asyncio.create_task(self.watch_assignations())
        self._watch_assignations_task.add_done_callback(self.log_assignation_fail)
        self._watch_assraces_task = asyncio.create_task(self.watch_assraces())
        self._watching = True

    def log_assignation_fail(self, future):
        return

    async def stop_watching(self):
        self._watch_assignations_task.cancel()
        self._watch_assraces_task.cancel()

        try:
            await asyncio.gather(
                self._watch_assignations_task,
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
