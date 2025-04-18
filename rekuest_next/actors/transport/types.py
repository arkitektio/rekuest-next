from typing import Any, List, Protocol, runtime_checkable


from rekuest_next.actors.types import Passport
from rekuest_next.messages import Assign
from rekuest_next.api.schema import AssignationEventKind, LogLevel


@runtime_checkable
class ActorTransport(Protocol):
    passport: Passport

    async def log_event(
        self,
        message: str = None,
        level: LogLevel = None,
    ): ...

    def spawn(self, assignment: Assign) -> "AssignTransport": ...


@runtime_checkable
class AssignTransport(Protocol):
    assignment: Assign
    
    
    async def send_progress(
        self,
        progress: int = None,
        message: str = None,
    ): ...
    
    async def send_done(self): ...
    async def send_error(self, error: str): ...
    async def send_critical(self, error: str): ...
    async def send_yield(self, returns: List[Any] = None): ...
    async def send_interrupted(self): ...
    async def send_collected(self): ...
    
