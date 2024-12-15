from typing import Any, List, Protocol, runtime_checkable


from rekuest_next.actors.types import Passport
from rekuest_next.messages import Assign
from rekuest_next.api.schema import ProvisionEventKind, AssignationEventKind, LogLevel


@runtime_checkable
class ActorTransport(Protocol):
    passport: Passport

    async def log_event(
        self,
        kind: ProvisionEventKind = None,
        message: str = None,
        level: LogLevel = None,
    ): ...

    def spawn(self, assignment: Assign) -> "AssignTransport": ...


@runtime_checkable
class AssignTransport(Protocol):
    assignment: Assign

    async def log_event(
        self,
        kind: AssignationEventKind = None,
        message: str = None,
        returns: List[Any] = None,
        progress: int = None,
    ): ...
