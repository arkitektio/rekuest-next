from typing import Protocol
from .errors import (
    DefiniteConnectionFail,
    CorrectableConnectionFail,
    AgentConnectionFail,
)
from rekuest_next.messages import ToAgentMessage


class TransportCallbacks(Protocol):
    async def abroadcast(
        self,
        message: ToAgentMessage,
    ) -> None: ...

    async def on_agent_error(self: AgentConnectionFail) -> None: ...

    async def on_definite_error(self, error: DefiniteConnectionFail) -> None: ...

    async def on_correctable_error(self, error: CorrectableConnectionFail) -> bool: ...
