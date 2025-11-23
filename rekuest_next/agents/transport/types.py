"""Transport types for agents."""

from typing import Protocol, runtime_checkable
import typing
from rekuest_next.messages import ToAgentMessage, FromAgentMessage


@runtime_checkable
class AgentTransport(Protocol):
    """Protocol for transport."""

    def aconnect(self, instance_id: str) -> typing.AsyncIterator[ToAgentMessage]:
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

    async def __aexit__(
        self, exc_type: typing.Any, exc_value: typing.Any, traceback: typing.Any
    ) -> None:
        """Exit the transport context."""
        ...
