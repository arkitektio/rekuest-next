from typing import Optional
from pydantic import BaseModel
from rekuest_next.api.schema import AssignationEventKind, LogLevel
from koil import unkoil
from rekuest_next.actors.types import Assignment
from rekuest_next.actors.transport.types import (
    ActorTransport,
    AssignTransport,
    Passport,
)


class AssignmentHelper(BaseModel):
    passport: Passport
    assignment: Assignment
    transport: AssignTransport

    async def alog(self, level: LogLevel, message: str) -> None:
        await self.transport.log_event(kind=AssignationEventKind.LOG, message=message)

    async def aprogress(self, progress: int, message: Optional[str] = None) -> None:
        await self.transport.log_event(
            kind=AssignationEventKind.PROGRESS,
            progress=progress,
            message=message,
        )

    def progress(self, progress: int, message:  Optional[str] = None) -> None:
        return unkoil(self.aprogress, progress, message=message)

    def log(self, level: LogLevel, message: str) -> None:
        return unkoil(self.alog, level, message)

    @property
    def user(self) -> str:
        return self.assignment.user

    @property
    def assignation(self) -> str:
        """Returns the governing assignation that cause the chained that lead to this execution"""
        return self.assignment.assignation

    class Config:
        arbitrary_types_allowed = True
