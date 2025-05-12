"""Transport types for agents."""

from typing import Protocol
from .errors import (
    DefiniteConnectionFail,
    CorrectableConnectionFail,
    AgentConnectionFail,
)
from rekuest_next.messages import ToAgentMessage


class AgentTransport(Protocol):
    """Protocol for transport."""

    async def aconnect(self) -> None:
        """Connect to the transport."""
        ...

    async def adisconnect(self) -> None:
        """Disconnect from the transport."""
        ...

    async def asend(self, message: ToAgentMessage) -> None:
        """Send a message to the transport."""
        ...

    def set_callback(self, callback: "TransportCallbacks") -> None:
        """Set the callback for the transport."""
        ...

    async def areceive(self) -> ToAgentMessage:
        """Receive a message from the transport."""
        ...


class TransportCallbacks(Protocol):
    """Protocol for transport callbacks."""

    async def abroadcast(
        self,
        message: ToAgentMessage,
    ) -> None:
        """Broadcast a message to all agents."""
        ...

    async def on_agent_error(self, error: AgentConnectionFail) -> None:
        """Handle an error from the agent."""
        ...

    async def on_definite_error(self, error: DefiniteConnectionFail) -> None:
        """Handle a definite error."""
        ...

    async def on_correctable_error(self, error: CorrectableConnectionFail) -> bool:
        """Handle a correctable error."""
        ...
