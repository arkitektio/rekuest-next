"""Transport types for agents."""

from typing import AsyncGenerator, Protocol, runtime_checkable
import typing
from rekuest_next.messages import FromAgentMessage, ToAgentMessage


@runtime_checkable
class AgentTransport(Protocol):
    """Protocol for transport."""

    async def aconnect(self, instance_id: str) -> None:
        """Connect to the transport."""
        ...

    async def adisconnect(self) -> None:
        """Disconnect from the transport."""
        ...

    async def asend(self, message: FromAgentMessage) -> None:
        """Send a message to the transport."""
        ...

    async def __aenter__(self) -> "AgentTransport":
        """Enter the transport context."""
        ...

    def areceive(self) -> AsyncGenerator[ToAgentMessage, None]:
        """Receive a message from the transport."""
        ...

    async def __aexit__(
        self, exc_type: typing.Any, exc_value: typing.Any, traceback: typing.Any
    ) -> None:
        """Exit the transport context."""
        ...
