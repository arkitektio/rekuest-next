"""No-Docker checks for the agent transport's connection lifecycle.

The socket is owned by the transport's connection task, not by the ``areceive()``
iterator. That is what lets an agent publish while it tears down: cancelling the
consumer (the agent loop) must leave the connection up, and only ``adisconnect()``
closes it — after flushing whatever is still queued.
"""

import asyncio
from typing import AsyncIterator, List, cast

import pytest
import websockets
from websockets.exceptions import ConnectionClosedError
from websockets.frames import Close

from rekuest_next import messages
from rekuest_next.agents.transport.errors import AgentWasKicked
from rekuest_next.agents.transport.websocket import KICK_CODE, WebsocketAgentTransport


DROP = object()


class FakeSocket:
    """Stands in for a live websockets client connection."""

    def __init__(self) -> None:
        self.sent: List[str] = []
        self.closed = False
        self._incoming: asyncio.Queue[object] = asyncio.Queue()

    def feed(self, message: messages.ToAgentMessage) -> None:
        self._incoming.put_nowait(message.model_dump_json())

    def drop(self, code: int = 1011) -> None:
        """Make the connection die under the transport, as a lost socket would."""
        self._incoming.put_nowait((DROP, code))

    async def send(self, message: str) -> None:
        await asyncio.sleep(0.01)  # a close that did not flush would outrun this
        self.sent.append(message)

    async def close(self) -> None:
        self.closed = True
        self._incoming.put_nowait(None)

    def __aiter__(self) -> AsyncIterator[str]:
        return self

    async def __anext__(self) -> str:
        message = await self._incoming.get()
        if isinstance(message, tuple) and message[0] is DROP:
            raise ConnectionClosedError(Close(message[1], "dropped"), None)
        if message is None:
            raise StopAsyncIteration
        return cast(str, message)


class FakeConnect:
    """Async context manager standing in for ``websockets.connect``."""

    def __init__(self, socket: FakeSocket) -> None:
        self.socket = socket

    async def __aenter__(self) -> FakeSocket:
        return self.socket

    async def __aexit__(self, *args: object) -> None:
        await self.socket.close()


async def _token() -> str:
    return "token"


@pytest.fixture()
def socket(monkeypatch: pytest.MonkeyPatch) -> FakeSocket:
    fake = FakeSocket()
    monkeypatch.setattr(
        websockets, "connect", lambda *args, **kwargs: FakeConnect(fake)
    )
    return fake


@pytest.mark.asyncio
async def test_socket_outlives_a_cancelled_receiver(socket: FakeSocket) -> None:
    """Cancelling the consumer must not take the connection down with it."""
    transport = WebsocketAgentTransport(
        endpoint_url="ws://localhost:8000/agi", token_loader=_token
    )

    async with transport as transport:
        await transport.aconnect()

        received: List[messages.ToAgentMessage] = []

        async def consume() -> None:
            async for message in transport.areceive():
                received.append(message)

        consumer = asyncio.create_task(consume())
        socket.feed(messages.Init(agent="agent-1"))
        await asyncio.sleep(0.05)
        assert len(received) == 1, "The consumer should have seen the Init"

        # This is what the agent loop's cancellation does.
        consumer.cancel()
        try:
            await consumer
        except asyncio.CancelledError:
            pass
        await asyncio.sleep(0.05)

        assert not socket.closed, "The socket must survive the cancelled consumer"

        # ... so the agent can still publish while it tears down.
        await transport.asend(messages.HeartbeatEvent())
        await transport.adisconnect()

        assert socket.closed, "adisconnect should close the socket"
        assert any("heartbeat" in message.lower() for message in socket.sent), (
            f"The teardown-time message should have been flushed, got {socket.sent}"
        )


@pytest.mark.asyncio
async def test_adisconnect_flushes_everything_still_queued(socket: FakeSocket) -> None:
    transport = WebsocketAgentTransport(
        endpoint_url="ws://localhost:8000/agi", token_loader=_token
    )

    async with transport as transport:
        await transport.aconnect()
        await asyncio.sleep(0.05)  # let it connect and register
        socket.sent.clear()

        for _ in range(5):
            await transport.asend(messages.HeartbeatEvent())

        await transport.adisconnect()

        assert len(socket.sent) == 5, (
            f"All queued messages should be on the wire, got {socket.sent}"
        )
        assert transport._send_queue.qsize() == 0


@pytest.mark.asyncio
async def test_reconnects_after_a_dropped_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lost socket is retried, transparently to the ``areceive()`` consumer.

    The consumer must not see a spurious end of stream, and a message queued while
    the connection was down must go out once it is back.
    """
    first, second = FakeSocket(), FakeSocket()
    sockets = iter([first, second])
    monkeypatch.setattr(
        websockets, "connect", lambda *args, **kwargs: FakeConnect(next(sockets))
    )

    transport = WebsocketAgentTransport(
        endpoint_url="ws://localhost:8000/agi",
        token_loader=_token,
        time_between_retries=0,
    )

    async with transport as transport:
        await transport.aconnect()

        received: List[messages.ToAgentMessage] = []
        ended = False

        async def consume() -> None:
            nonlocal ended
            async for message in transport.areceive():
                received.append(message)
            ended = True

        consumer = asyncio.create_task(consume())

        first.feed(messages.Init(agent="agent-1"))
        await asyncio.sleep(0.05)

        first.drop()
        await asyncio.sleep(0.05)

        # Published while the transport is between sockets.
        await transport.asend(messages.HeartbeatEvent())
        await asyncio.sleep(0.1)

        second.feed(messages.Init(agent="agent-1"))
        await asyncio.sleep(0.05)

        assert len(received) == 2, (
            f"The consumer should have seen both Inits across the reconnect, got {received}"
        )
        assert not ended, "The consumer must not see the reconnect as an end of stream"
        assert any("heartbeat" in message.lower() for message in second.sent), (
            f"The message queued while down should go out after reconnect, got {second.sent}"
        )

        await transport.adisconnect()
        consumer.cancel()
        try:
            await consumer
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_a_kick_close_code_surfaces_to_the_consumer(socket: FakeSocket) -> None:
    """A close code the backend uses to reject the agent is not a reconnect."""
    transport = WebsocketAgentTransport(
        endpoint_url="ws://localhost:8000/agi",
        token_loader=_token,
        time_between_retries=0,
    )

    async with transport as transport:
        await transport.aconnect()

        async def consume() -> None:
            async for _ in transport.areceive():
                pass

        consumer = asyncio.create_task(consume())
        await asyncio.sleep(0.05)
        socket.drop(code=KICK_CODE)

        with pytest.raises(AgentWasKicked):
            await asyncio.wait_for(consumer, timeout=1)


@pytest.mark.asyncio
async def test_adisconnect_without_a_live_socket_does_not_hang() -> None:
    """With no connection there is nobody to flush to — closing must not block."""
    transport = WebsocketAgentTransport(
        endpoint_url="ws://localhost:8000/agi", token_loader=_token
    )

    async with transport as transport:
        await transport.asend(messages.HeartbeatEvent())

        await asyncio.wait_for(transport.adisconnect(), timeout=1)

    assert transport._send_queue.qsize() == 1, "The message has nowhere to go"
