"""An in-memory :class:`AgentTransport` for driving an agent without a backend.

The shipped fakes could not do this. Two of them (``test_agent_postman`` and
``test_postman_cancel``, byte-identical) only recorded ``asend`` and had no ``areceive``,
so they could serve ``AgentPostman`` but never a ``BaseAgent`` message loop; the third
substitutes the *socket* under the real websocket transport, which is the right tool for
testing the transport itself but not for testing what the agent does with messages.

This one satisfies the whole contract, so an agent can be run against it end to end:
feed inbound messages with :meth:`feed`, read what the agent emitted from :attr:`sent`.
"""

import asyncio
from types import TracebackType
from typing import Optional, Self, TypeVar
from collections.abc import AsyncIterator

from rekuest_next import messages
from rekuest_next.agents.transport.base import AgentTransport

_CLOSED = object()

T = TypeVar("T", bound=messages.FromAgentMessage)


class MemoryAgentTransport(AgentTransport):
    """A queue-backed transport that records what the agent sends."""

    sent: list[messages.FromAgentMessage] = []
    """Every outbound message, in order, including the ``seq`` the agent stamped."""

    _in_queue: Optional["asyncio.Queue[object]"] = None
    _connected: bool = False

    def model_post_init(self, __context: object) -> None:
        """Give every instance its own recording list and queue."""
        self.sent = []
        self._in_queue = asyncio.Queue()

    # -- inbound -------------------------------------------------------------------

    def feed(self, message: messages.ToAgentMessage) -> None:
        """Hand the agent a message, as the backend would."""
        self._queue.put_nowait(message)

    def fail(self, error: BaseException) -> None:
        """Make the stream raise, as a terminal connection failure does."""
        self._queue.put_nowait(error)

    def close_stream(self) -> None:
        """End the stream, as a closed connection does."""
        self._queue.put_nowait(_CLOSED)

    @property
    def _queue(self) -> "asyncio.Queue[object]":
        if self._in_queue is None:  # pragma: no cover - guarded by model_post_init
            raise RuntimeError("Transport was not entered")
        return self._in_queue

    async def areceive(self) -> AsyncIterator[messages.ToAgentMessage]:
        """Yield fed messages until the stream is closed."""
        while True:
            item = await self._queue.get()
            if item is _CLOSED:
                return
            if isinstance(item, BaseException):
                raise item
            assert isinstance(item, messages.Message)
            yield item

    # -- outbound ------------------------------------------------------------------

    async def asend(self, message: messages.FromAgentMessage) -> None:
        """Record an outbound message instead of putting it on a wire."""
        self.sent.append(message)

    def of_type(self, kind: type[T]) -> list[T]:
        """Every recorded message of one type, for readable assertions."""
        return [m for m in self.sent if isinstance(m, kind)]

    # -- lifecycle -----------------------------------------------------------------

    @property
    def connected(self) -> bool:
        """Whether :meth:`aconnect` has run and :meth:`adisconnect` has not."""
        return self._connected

    async def aconnect(self) -> None:
        """Mark the transport connected. There is no socket to open."""
        self._connected = True

    async def adisconnect(self) -> None:
        """Mark the transport disconnected and end the stream."""
        self._connected = False
        self.close_stream()

    async def drop_link(self) -> None:
        """Simulate the socket dropping while the transport keeps retrying.

        The stream deliberately stays open: that is the whole point of the window
        this models. The real websocket transport reconnects transparently, so the
        agent's message loop never ends and the only signal it gets is this
        callback.
        """
        self._connected = False
        await self.anotify_connection_change(False)

    async def restore_link(self) -> None:
        """Simulate the transport getting its socket back."""
        self._connected = True
        await self.anotify_connection_change(True)

    async def __aenter__(self) -> Self:
        """Enter the transport context."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Leave the transport context."""
        await self.adisconnect()
