"""A GraphQL postman"""

from types import TracebackType
from typing import AsyncGenerator, Dict
from rekuest_next.api.schema import (
    AssignationEvent,
    Assignation,
    aassign,
    awatch_assignations,
    acancel,
    AssignInput,
)
import asyncio
from pydantic import Field, PrivateAttr
import logging
from .errors import PostmanException
from rekuest_next.rath import RekuestNextRath
from koil.composition import KoiledModel
from .vars import current_postman

logger = logging.getLogger(__name__)


class GraphQLPostman(KoiledModel):
    """A GraphQL Postman

    This postman is used to send messages to the GraphQL server via a graphql
    transport.

    This graphql postman

    """

    rath: RekuestNextRath
    connected: bool = Field(default=False)
    instance_id: str = Field(description="The instance_id of the waiter")
    assignations: Dict[str, Assignation] = Field(default_factory=dict)

    _ass_update_queues: Dict[str, asyncio.Queue[AssignationEvent]] = PrivateAttr(
        default_factory=lambda: {}
    )
    _ass_update_queue: asyncio.Queue[AssignationEvent] | None = None
    _watch_assraces_task: asyncio.Task[None] | None = None
    _watch_assignations_task: asyncio.Task[None] | None = None

    _watching: bool = PrivateAttr(default=False)
    _lock: asyncio.Lock | None = None
    _received_something: bool = False

    async def aassign(
        self, assign: AssignInput
    ) -> AsyncGenerator[AssignationEvent, None]:
        """Assign a"""
        if not self._received_something:
            await asyncio.sleep(0.5)  # Add an initial sleep

        if not assign.reference:
            raise Exception("Reference must be set. Before assigning")

        if not self._lock:
            raise ValueError("Postman was never connected")

        async with self._lock:
            if not self._watching:
                await self.start_watching()

        self._ass_update_queues[assign.reference] = asyncio.Queue()
        queue = self._ass_update_queues[assign.reference]

        try:
            assignation = await aassign(**assign.model_dump())
        except Exception as e:
            raise PostmanException(f"Cannot Assign: {e}") from e

        try:
            while True:
                signal = await queue.get()
                yield signal
                queue.task_done()

        except asyncio.CancelledError as e:
            await acancel(assignation=assignation.id)
            # TODO: Wait for cancellation to succeed
            del self._ass_update_queues[assign.reference]
            raise e

    def unregister_assignation_queue(self, ass_id: str) -> None:
        """Delte the watch queue"""
        del self._ass_update_queues[ass_id]

    async def watch_assignations(self) -> None:
        """Watch assingaitons task"""
        try:
            async for assignation in awatch_assignations(
                self.instance_id, rath=self.rath
            ):
                self._received_something = True
                if assignation.event:
                    reference = assignation.event.reference
                    if reference not in self._ass_update_queues:
                        logger.critical(
                            "Race connection. Maybe there was a disconnect?"
                        )
                    else:
                        await self._ass_update_queues[reference].put(assignation.event)
                if assignation.create:
                    if assignation.create.reference not in self._ass_update_queues:
                        logger.critical("RACE CONDITION EXPERIENCED")

        except Exception as e:
            logger.error("Watching Assignations failed", exc_info=True)
            raise e

    async def watch_assraces(self) -> None:
        """Checks for new assignaitons in the update_queue

        Websockets can be faster than http, therefore we put stuff in a queue first
        """
        assert self._ass_update_queue is not None, "Needs to be set"

        try:
            while True:
                ass: AssignationEvent = await self._ass_update_queue.get()
                self._ass_update_queue.task_done()
                logger.info(f"Postman received Assignation {ass}")

                unique_identifier = ass.reference

                print(f"Received assignation event with reference: {ass}")

                await self._ass_update_queues[unique_identifier].put(ass)

        except Exception:
            logger.error("Error in watch_resraces", exc_info=True)

    async def start_watching(self) -> None:
        """Start watching for updates"""
        logger.info("Starting watching")
        self._ass_update_queue = asyncio.Queue()
        self._watch_assignations_task = asyncio.create_task(self.watch_assignations())
        self._watch_assignations_task.add_done_callback(self.log_assignation_fail)
        self._watch_assraces_task = asyncio.create_task(self.watch_assraces())
        self._watching = True

    def log_assignation_fail(self, task: asyncio.Task[None]) -> None:
        """a hook to"""
        return

    async def stop_watching(self) -> None:
        """Causes the postman to stop watching"""
        if self._watch_assignations_task and self._watch_assraces_task:
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

    async def __aenter__(self) -> "GraphQLPostman":
        """Enter the postman"""
        self._lock = asyncio.Lock()
        current_postman.set(self)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context manager"""
        if self._watching:
            await self.stop_watching()
        current_postman.set(None)
        return await super().__aexit__(exc_type, exc_val, exc_tb)
