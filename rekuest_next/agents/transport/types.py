from typing import Protocol, Callable, Awaitable, Union
from pydantic import Field
from .errors import (
    DefiniteConnectionFail,
    CorrectableConnectionFail,
    AgentConnectionFail,
)
from rekuest_next.messages import (
    Assignation,
    Unassignation,
    Provision,
    Unprovision,
    Inquiry,
)


class TransportCallbacks(Protocol):
    async def abroadcast(
        self,
        message: Union[Assignation, Unassignation, Unprovision, Provision, Inquiry],
    ) -> None:
        ...

    async def on_agent_error(self: AgentConnectionFail) -> None:
        ...

    async def on_definite_error(self, error: DefiniteConnectionFail) -> None:
        ...

    async def on_correctable_error(self, error: CorrectableConnectionFail) -> bool:
        ...
