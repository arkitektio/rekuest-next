from typing import Optional
from pydantic import BaseModel, ConfigDict
from rekuest_next.api.schema import AssignationEventKind, LogLevel
from koil import unkoil
from rekuest_next import messages
from rekuest_next.actors.vars import (
    current_assignation_helper,
)
from rekuest_next.actors.base import Actor

class AssignmentHelper(BaseModel):
    assignment: messages.Assign
    actor: Actor
    model_config = ConfigDict(arbitrary_types_allowed=True)
    _token = None

    async def alog(self, level: LogLevel, message: str) -> None:
        await self.actor.asend(
            message=messages.LogEvent(
                assignation=self.assignment.assignation,
                level=level,
                message=message,
            )
        )

    async def aprogress(self, progress: int, message: Optional[str] = None) -> None:
        await self.actor.asend(
            message=messages.ProgressEvent(
                assignation=self.assignment.assignation,
                percentage=progress,
                messages=message,
            )
        )
        
    async def abreakpoint(self) -> None:
        """Check if the actor needs to break"""
        await self.actor.abreak(self.assignment.assignation)
        #await self.actor.acheck_needs_break()
        
    def breakpoint(self) -> None:
        return unkoil(self.abreakpoint)

    def progress(self, progress: int, message: Optional[str] = None) -> None:
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


    def __enter__(self):
        self._token = current_assignation_helper.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        current_assignation_helper.reset(self._token)

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)