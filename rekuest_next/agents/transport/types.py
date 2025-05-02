"""Transport types for agents."""

from typing import Protocol
from .errors import (
    DefiniteConnectionFail,
    CorrectableConnectionFail,
    AgentConnectionFail,
)
from rekuest_next.messages import ToAgentMessage


class TransportCallbacks(Protocol):
    """Protocol for transport callbacks."""

    async def abroadcast(
        self,
        message: ToAgentMessage,
    ) -> None:
        """Broadcast a message to all agents."""
        ...

    async def on_agent_error(self: AgentConnectionFail) -> None:
        """Handle an error from the agent."""
        ...

    async def on_definite_error(self, error: DefiniteConnectionFail) -> None:
        """Handle a definite error."""
        ...

    async def on_correctable_error(self, error: CorrectableConnectionFail) -> bool:
        """Handle a correctable error."""
        ...
