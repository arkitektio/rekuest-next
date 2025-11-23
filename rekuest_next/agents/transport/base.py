"""Agent Transport Base Class"""

from abc import abstractmethod
from types import TracebackType
from typing import Optional, Self, AsyncIterator

from pydantic import ConfigDict, PrivateAttr

from rekuest_next.messages import FromAgentMessage, ToAgentMessage

from koil.composition import KoiledModel


class AgentTransport(KoiledModel):
    """Agent Transport

    A Transport is a means of communicating with an Agent. It is responsible for sending
    and receiving messages from the backend. It needs to implement the following methods:

    list_provision: Getting the list of active provisions from the backend. (depends on the backend)
    list_assignation: Getting the list of active assignations from the backend. (depends on the backend)

    change_assignation: Changing the status of an assignation. (depends on the backend)
    change_provision: Changing the status of an provision. (depends on the backend)

    broadcast: Configuring the callbacks for the transport on new assignation, unassignation provision and unprovison.

    if it is a stateful connection it can also implement the following methods:

    aconnect
    adisconnect

    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def connected(self) -> bool:
        """Return True if the transport is connected."""
        raise NotImplementedError("Implement this method")

    @abstractmethod
    async def asend(self, message: FromAgentMessage) -> None:
        """Send a message to the agent."""
        raise NotImplementedError("This is an abstract Base Class")

    @abstractmethod
    async def aconnect(self, instance_id: str) -> None:
        """Connect to the agent."""
        raise NotImplementedError("This is an abstract Base Class")
        yield

    @abstractmethod
    async def areceive(self) -> AsyncIterator[ToAgentMessage]:
        """Receive messages from the agent."""
        raise NotImplementedError("This is an abstract Base Class")
        yield

    @abstractmethod
    async def adisconnect(self) -> None:
        """Disconnect the agent."""
        raise NotImplementedError("This is an abstract Base Class")

    async def __aenter__(self) -> Self:  # noqa: ANN001
        """Enter the context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context manager."""
        raise NotImplementedError("This is an abstract Base Class")
