"""A GraphQL postman"""

from types import TracebackType
from typing import AsyncGenerator, Dict
from rekuest_next.api.schema import (
    TaskEvent,
    Task,
    aassign,
    awatch_tasks,
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
    tasks: Dict[str, Task] = Field(default_factory=dict)
    cancel_timeout: float = Field(
        default=5.0,
        description="Maximum seconds to wait for the server to confirm cancellation of a task when an assign stream is cancelled. Bounds cancellation so cancelling a call can never hang.",
    )

    _ass_update_queues: Dict[str, asyncio.Queue[TaskEvent]] = PrivateAttr(
        default_factory=lambda: {}
    )
    _ass_update_queue: asyncio.Queue[TaskEvent] | None = None
    _watch_assraces_task: asyncio.Task[None] | None = None
    _watch_tasks_task: asyncio.Task[None] | None = None

    _watching: bool = PrivateAttr(default=False)
    _lock: asyncio.Lock | None = None
    _received_something: bool = False

    async def aassign(
        self, assign: AssignInput
    ) -> AsyncGenerator[TaskEvent, None]:
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
            task = await aassign(**assign.model_dump(), rath=self.rath)
        except Exception as e:
            raise PostmanException(f"Cannot Assign: {e}") from e

        try:
            while True:
                signal = await queue.get()
                yield signal
                queue.task_done()

        except asyncio.CancelledError as e:
            # Best-effort: tell the server to cancel the task, but never let
            # confirming the cancellation hang the caller. If the connection is in a
            # bad state the mutation can stall indefinitely, so bound it.
            try:
                await asyncio.wait_for(
                    acancel(task=task.id, rath=self.rath),
                    timeout=self.cancel_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Timed out confirming cancellation of task %s",
                    task.id,
                )
            except Exception:
                logger.warning(
                    "Failed to cancel task %s", task.id, exc_info=True
                )
            finally:
                self._ass_update_queues.pop(assign.reference, None)
            raise e

    async def watch_tasks(self) -> None:
        """Watch assingaitons task"""
        try:
            async for task in awatch_tasks(rath=self.rath):
                self._received_something = True
                if task.event:
                    reference = task.event.reference
                    if reference not in self._ass_update_queues:
                        logger.critical(
                            "Race connection. Maybe there was a disconnect?"
                        )
                    else:
                        await self._ass_update_queues[reference].put(task.event)
                if task.create:
                    if task.create.reference not in self._ass_update_queues:
                        logger.critical("RACE CONDITION EXPERIENCED")

        except Exception as e:
            logger.error("Watching Tasks failed", exc_info=True)
            raise e

    async def watch_assraces(self) -> None:
        """Checks for new assignaitons in the update_queue

        Websockets can be faster than http, therefore we put stuff in a queue first
        """
        assert self._ass_update_queue is not None, "Needs to be set"

        try:
            while True:
                ass: TaskEvent = await self._ass_update_queue.get()
                self._ass_update_queue.task_done()
                logger.info(f"Postman received Task {ass}")

                unique_identifier = ass.reference

                await self._ass_update_queues[unique_identifier].put(ass)

        except Exception:
            logger.error("Error in watch_resraces", exc_info=True)

    async def start_watching(self) -> None:
        """Start watching for updates"""
        logger.info("Starting watching")
        self._ass_update_queue = asyncio.Queue()
        self._watch_tasks_task = asyncio.create_task(self.watch_tasks())
        self._watch_tasks_task.add_done_callback(self.log_task_fail)
        self._watch_assraces_task = asyncio.create_task(self.watch_assraces())
        self._watching = True

    def log_task_fail(self, task: asyncio.Task[None]) -> None:
        """a hook to"""
        return

    async def stop_watching(self) -> None:
        """Causes the postman to stop watching"""
        if self._watch_tasks_task and self._watch_assraces_task:
            self._watch_tasks_task.cancel()
            self._watch_assraces_task.cancel()

            try:
                await asyncio.gather(
                    self._watch_tasks_task,
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
