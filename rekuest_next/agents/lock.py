import asyncio
from rekuest_next.api.schema import LockSchemaInput
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rekuest_next.actors.types import Agent


class TaskLock:
    def __init__(self, agent: "Agent", lock_schema: "LockSchemaInput"):
        self.agent = agent
        self.lock = asyncio.Lock()
        self.locking_task = None
        self.lock_schema = lock_schema

    async def acquire(self, assignation: str) -> None:
        await self.lock.acquire()
        self.locking_task = assignation
        await self.agent.alock(self.lock_schema.key, assignation)

    async def release(self) -> None:
        self.lock.release()
        await self.agent.aunlock(self.lock_schema.key)
        self.locking_task = None

    async def get(self, assignation: str) -> "AssignationLock":
        return AssignationLock(self, assignation, lock_schema=self.lock_schema)


class AssignationLock:
    def __init__(
        self, task_lock: TaskLock, assignation: str, lock_schema: "LockSchemaInput"
    ):
        self.agent = task_lock.agent
        self.assignation = assignation
        self.lock_schema = lock_schema
        self.task_lock = task_lock

    async def __aenter__(self):
        await self.task_lock.lock.acquire()
        self.task_lock.locking_task = self.assignation
        await self.agent.alock(self.lock_schema.key, self.assignation)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.task_lock.lock.release()
        self.task_lock.locking_task = None
        await self.agent.aunlock(self.lock_schema.key)
