import asyncio
from rekuest_next.api.schema import LockDefinitionInput, LockImplementationInput
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rekuest_next.actors.types import Agent


class TaskLock:
    def __init__(self, agent: "Agent", lock: "LockImplementationInput"):
        self.agent = agent
        self.lock = asyncio.Lock()
        self.lock_key = lock.definition.key
        self.locking_task = None
        self.definition = lock.definition

    async def acquire(self, assignation: str) -> None:
        await self.lock.acquire()
        self.locking_task = assignation
        await self.agent.alock(self.definition.key, assignation)

    async def release(self) -> None:
        self.lock.release()
        await self.agent.aunlock(self.lock_key)
        self.locking_task = None

    async def get(self, assignation: str) -> "AssignationLock":
        return AssignationLock(self, assignation, definition=self.definition)


class AssignationLock:
    def __init__(
        self,
        task_lock: TaskLock,
        assignation: str,
        definition: "LockDefinitionInput",
    ):
        self.agent = task_lock.agent
        self.assignation = assignation
        self.definition = definition
        self.task_lock = task_lock

    async def __aenter__(self):
        await self.task_lock.lock.acquire()
        self.task_lock.locking_task = self.assignation
        await self.agent.alock(self.definition.key, self.assignation)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.task_lock.lock.release()
        self.task_lock.locking_task = None
        await self.agent.aunlock(self.definition.key)
