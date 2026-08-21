"""No-Docker checks for the agent transport's connection lifecycle.

The socket is owned by the transport's connection task, not by the ``areceive()``
iterator. That is what lets an agent publish while it tears down: cancelling the
consumer (the agent loop) must leave the connection up, and only ``adisconnect()``
closes it — after flushing whatever is still queued.
"""

import asyncio
import json
import time
from typing import AsyncIterator, List, cast

import pytest
import websockets
from websockets.exceptions import ConnectionClosedError
from websockets.frames import Close

from rekuest_next import messages
from rekuest_next.agents.policy import Backoff, ConnectionPolicy
from rekuest_next.agents.transport.errors import AgentWasKicked, DefiniteConnectionFail
from rekuest_next.agents.transport.types import HandshakeParams
from rekuest_next.agents.transport.websocket import KICK_CODE, WebsocketAgentTransport


DROP = object()


class FakeSocket:
    """Stands in for a live websockets client connection."""

    def __init__(self) -> None:
        self.sent: List[str] = []
        self.closed = False
        self._dropped: int | None = None
        self._incoming: asyncio.Queue[object] = asyncio.Queue()

    def feed(self, message: messages.ToAgentMessage) -> None:
        self._incoming.put_nowait(message.model_dump_json())

    def drop(self, code: int = 1011) -> None:
        """Make the connection die under the transport, as a lost socket would."""
        self._dropped = code
        self._incoming.put_nowait((DROP, code))

    async def send(self, message: str) -> None:
        await asyncio.sleep(0.01)  # a close that did not flush would outrun this
        if self._dropped is not None:
            # A real socket fails the send that was in flight when it died, rather
            # than quietly accepting it.
            raise ConnectionClosedError(Close(self._dropped, "dropped"), None)
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


_NO_DELAY = Backoff(initial=0.0, factor=1.0, max=0.0, jitter=0.0)


class _Host:
    """Stands in for the agent: supplies the policy and records link transitions."""

    def __init__(
        self,
        policy: ConnectionPolicy | None = None,
        session_id: str = "session",
        force: bool | None = None,
    ) -> None:
        self.connection_policy = policy or ConnectionPolicy()
        self.session_id = session_id
        self.force = force
        self.transitions: List[bool] = []

    async def aget_handshake_params(self) -> HandshakeParams:
        return HandshakeParams(force=self.force, session_id=self.session_id)

    async def aon_connection_change(self, healthy: bool) -> None:
        self.transitions.append(healthy)


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
    )
    transport.set_transport_host(_Host(ConnectionPolicy(backoff=_NO_DELAY)))

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
    )
    transport.set_transport_host(_Host(ConnectionPolicy(backoff=_NO_DELAY)))

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


def _register_frames(socket: FakeSocket) -> List[messages.Register]:
    """Every Register the transport put on this socket."""
    frames: List[messages.Register] = []
    for raw in socket.sent:
        payload = json.loads(raw)
        if payload.get("type") == messages.FromAgentMessageType.REGISTER.value:
            frames.append(messages.Register(**payload))
    return frames


class _Handshake:
    """Stands in for the agent, which is what owns the session id."""

    def __init__(self, session_id: str, force: bool | None = None) -> None:
        self.session_id = session_id
        self.force = force

    async def aget_handshake_params(self) -> HandshakeParams:
        return HandshakeParams(force=self.force, session_id=self.session_id)


@pytest.mark.asyncio
async def test_register_carries_the_agents_session_id(socket: FakeSocket) -> None:
    """The session id lives on the agent but has to go out in Register.

    It is the process-reclaim signal: reconnecting with the same session id tells the
    backend this process survived. Before the handshake was made explicit the transport
    built Register on its own and had no way to reach it, so it was never sent.
    """
    transport = WebsocketAgentTransport(
        endpoint_url="ws://localhost:8000/agi", token_loader=_token
    )
    transport.set_transport_host(_Handshake("session-abc"))

    async with transport as transport:
        await transport.aconnect()
        consumer = asyncio.create_task(_drain(transport))
        await asyncio.sleep(0.05)

        registers = _register_frames(socket)
        assert len(registers) == 1, f"expected one Register, got {socket.sent}"
        assert registers[0].session_id == "session-abc"
        assert registers[0].token == await _token()

        await transport.adisconnect()
        await _stop(consumer)


@pytest.mark.asyncio
async def test_handshake_is_reresolved_on_every_reconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reconnect must re-ask, not replay a handshake captured at build time."""
    first, second = FakeSocket(), FakeSocket()
    sockets = iter([first, second])
    monkeypatch.setattr(
        websockets, "connect", lambda *args, **kwargs: FakeConnect(next(sockets))
    )

    handshake = _Host(ConnectionPolicy(backoff=_NO_DELAY), session_id="session-1")
    transport = WebsocketAgentTransport(
        endpoint_url="ws://localhost:8000/agi",
        token_loader=_token,
    )
    transport.set_transport_host(handshake)

    async with transport as transport:
        await transport.aconnect()
        consumer = asyncio.create_task(_drain(transport))
        await asyncio.sleep(0.05)
        assert _register_frames(first)[0].session_id == "session-1"

        # The process "restarts": a new session id, which is the fail-and-cascade signal.
        handshake.session_id = "session-2"
        first.drop()
        await asyncio.sleep(0.1)

        assert _register_frames(second)[0].session_id == "session-2", (
            "the reconnect must present the current session id, not the original one"
        )

        await transport.adisconnect()
        await _stop(consumer)


@pytest.mark.asyncio
async def test_agent_force_overrides_the_transport_default(socket: FakeSocket) -> None:
    """The agent's per-run takeover policy wins; "no opinion" keeps the build-time one."""
    transport = WebsocketAgentTransport(
        endpoint_url="ws://localhost:8000/agi", token_loader=_token, force=True
    )
    # force=None means the agent has no opinion, so the transport's True stands.
    transport.set_transport_host(_Handshake("s", force=None))

    async with transport as transport:
        await transport.aconnect()
        consumer = asyncio.create_task(_drain(transport))
        await asyncio.sleep(0.05)
        assert _register_frames(socket)[0].force is True
        await transport.adisconnect()
        await _stop(consumer)


@pytest.mark.asyncio
async def test_connected_reports_the_live_socket(socket: FakeSocket) -> None:
    """``connected`` used to raise NotImplementedError on this transport."""
    transport = WebsocketAgentTransport(
        endpoint_url="ws://localhost:8000/agi", token_loader=_token
    )
    assert transport.connected is False

    async with transport as transport:
        await transport.aconnect()
        consumer = asyncio.create_task(_drain(transport))
        await asyncio.sleep(0.05)
        assert transport.connected is True

        await transport.adisconnect()
        await _stop(consumer)
        assert transport.connected is False


async def _drain(transport: WebsocketAgentTransport) -> None:
    """Consume the stream so the transport's sender task runs."""
    async for _ in transport.areceive():
        pass


async def _stop(task: "asyncio.Task[None]") -> None:
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# -- the agent-level connection policy ---------------------------------------------


@pytest.mark.asyncio
async def test_the_host_is_told_when_the_link_drops_and_returns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The signal the agent never used to get.

    ``areceive()`` deliberately does not end across a reconnect, so this callback is
    the only way anything above the transport can learn that control was lost.
    """
    first, second = FakeSocket(), FakeSocket()
    sockets = iter([first, second])
    monkeypatch.setattr(
        websockets, "connect", lambda *args, **kwargs: FakeConnect(next(sockets))
    )

    host = _Host(ConnectionPolicy(backoff=_NO_DELAY))
    transport = WebsocketAgentTransport(
        endpoint_url="ws://localhost:8000/agi", token_loader=_token
    )
    transport.set_transport_host(host)

    async with transport as transport:
        await transport.aconnect()
        consumer = asyncio.create_task(_drain(transport))
        await asyncio.sleep(0.05)
        assert host.transitions == [True], f"expected link-up, got {host.transitions}"

        first.drop()
        await asyncio.sleep(0.1)

        assert host.transitions == [True, False, True], (
            f"expected down-then-up across the reconnect, got {host.transitions}"
        )

        await transport.adisconnect()
        await _stop(consumer)


@pytest.mark.asyncio
async def test_a_short_lived_connection_does_not_refund_the_retry_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """What makes ``max_retries`` mean anything against a flapping link.

    The budget used to be reset by any successful connect at all, so a link that
    connected and immediately dropped retried forever. ``reset_after`` requires the
    connection to actually stand up before it counts as a recovery.
    """
    sockets = [FakeSocket() for _ in range(6)]
    handed_out = iter(sockets)
    monkeypatch.setattr(
        websockets, "connect", lambda *args, **kwargs: FakeConnect(next(handed_out))
    )

    # Every connection is far shorter than reset_after, so nothing is ever refunded.
    host = _Host(ConnectionPolicy(max_retries=2, backoff=_NO_DELAY, reset_after=30.0))
    transport = WebsocketAgentTransport(
        endpoint_url="ws://localhost:8000/agi", token_loader=_token
    )
    transport.set_transport_host(host)

    async with transport as transport:
        await transport.aconnect()

        failure: BaseException | None = None

        async def consume() -> None:
            nonlocal failure
            try:
                async for _ in transport.areceive():
                    pass
            except BaseException as exc:  # noqa: BLE001 - recorded for the assertion
                failure = exc

        consumer = asyncio.create_task(consume())

        for socket in sockets[:3]:
            await asyncio.sleep(0.03)
            socket.drop()
        await asyncio.sleep(0.15)

        assert isinstance(failure, DefiniteConnectionFail), (
            f"the budget must run out rather than retrying forever, got {failure!r}"
        )

        await transport.adisconnect()
        await _stop(consumer)


def test_deprecated_retry_knobs_still_win_and_warn() -> None:
    """Someone who explicitly built a transport with these meant them."""
    with pytest.warns(DeprecationWarning, match="deprecated"):
        transport = WebsocketAgentTransport(
            endpoint_url="ws://localhost:8000/agi",
            token_loader=_token,
            max_retries=10,
            time_between_retries=0,
        )
    transport.set_transport_host(_Host(ConnectionPolicy(max_retries=5)))

    policy = transport.connection_policy
    assert policy.max_retries == 10, "the explicit knob must override the agent policy"
    assert policy.backoff.delay_for(3) == 0, "a pinned delay must stay flat, not grow"


def test_allow_reconnect_false_maps_to_a_zero_budget() -> None:
    with pytest.warns(DeprecationWarning):
        transport = WebsocketAgentTransport(
            endpoint_url="ws://localhost:8000/agi",
            token_loader=_token,
            allow_reconnect=False,
        )
    assert transport.connection_policy.max_retries == 0


def test_a_transport_with_no_host_falls_back_to_the_default_policy() -> None:
    """The transport tests drive it bare; that must keep working."""
    transport = WebsocketAgentTransport(
        endpoint_url="ws://localhost:8000/agi", token_loader=_token
    )
    assert transport.connection_policy == ConnectionPolicy()


def test_flap_detection_gives_up_on_a_link_that_keeps_dropping() -> None:
    """The backstop for a link that stays up just long enough to refund the budget."""
    transport = WebsocketAgentTransport(
        endpoint_url="ws://localhost:8000/agi", token_loader=_token
    )
    policy = ConnectionPolicy(flap_limit=3, flap_window=300.0)

    assert not transport._is_flapping(policy)
    transport._drop_times.extend([time.monotonic()] * 3)
    assert transport._is_flapping(policy)

    # Old drops age out of the window rather than counting forever.
    transport._drop_times[:] = [time.monotonic() - 600.0] * 5
    assert not transport._is_flapping(policy)


def test_flap_detection_is_off_unless_asked_for() -> None:
    transport = WebsocketAgentTransport(
        endpoint_url="ws://localhost:8000/agi", token_loader=_token
    )
    transport._drop_times.extend([time.monotonic()] * 50)
    assert not transport._is_flapping(ConnectionPolicy())


@pytest.mark.asyncio
async def test_drop_history_does_not_leak_across_sessions() -> None:
    """Flap history is per-session, like every other piece of connection state.

    A transport reused across two ``async with`` blocks would otherwise carry the
    previous session's drops into the new one and trip flap detection on history
    that no longer applies.
    """
    transport = WebsocketAgentTransport(
        endpoint_url="ws://localhost:8000/agi", token_loader=_token
    )

    async with transport:
        transport._drop_times.extend([time.monotonic()] * 5)

    async with transport:
        assert transport._drop_times == [], (
            "a new session must start with a clean flap budget"
        )


@pytest.mark.asyncio
async def test_a_drop_while_a_send_is_in_flight_is_still_recoverable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The uncovered half of a dropped socket: the sender was mid-``send``.

    ``sending()`` used to catch only ``CancelledError``, so a ``ConnectionClosedError``
    raised inside ``client.send`` was stored on the task and re-raised by the
    connect loop's ``finally``. That replaced the in-flight ``CorrectableConnectionFail``
    and escaped the retry handler, turning a recoverable blip into a full agent
    teardown — taking every action with it, whatever its disconnect policy said.

    The existing reconnect test drops with an *idle* sender, which is exactly why
    this went unnoticed.
    """
    first, second = FakeSocket(), FakeSocket()
    sockets = iter([first, second])
    monkeypatch.setattr(
        websockets, "connect", lambda *args, **kwargs: FakeConnect(next(sockets))
    )

    transport = WebsocketAgentTransport(
        endpoint_url="ws://localhost:8000/agi", token_loader=_token
    )
    transport.set_transport_host(_Host(ConnectionPolicy(backoff=_NO_DELAY)))

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

        # Queue a message, then drop while the sender is parked inside client.send().
        await transport.asend(messages.HeartbeatEvent())
        await asyncio.sleep(0.005)
        first.drop()
        await asyncio.sleep(0.2)

        second.feed(messages.Init(agent="agent-1"))
        await asyncio.sleep(0.05)

        assert not ended, (
            "a drop during an in-flight send must still be retried, not fatal"
        )
        assert len(received) == 2, (
            f"the consumer should have seen both Inits across the reconnect, got {received}"
        )
        assert any("heartbeat" in message.lower() for message in second.sent), (
            f"the message being sent when the socket died must be requeued, got {second.sent}"
        )

        await transport.adisconnect()
        await _stop(consumer)


@pytest.mark.asyncio
async def test_a_failed_send_does_not_wedge_the_flush(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``task_done()`` must still be called for the get that failed.

    Skipping it leaves the queue's unfinished count permanently above zero, so
    ``aflush``'s ``join()`` can never complete again for that transport and every
    later disconnect burns the full ``flush_timeout``.
    """
    first, second = FakeSocket(), FakeSocket()
    sockets = iter([first, second])
    monkeypatch.setattr(
        websockets, "connect", lambda *args, **kwargs: FakeConnect(next(sockets))
    )

    transport = WebsocketAgentTransport(
        endpoint_url="ws://localhost:8000/agi", token_loader=_token
    )
    transport.set_transport_host(_Host(ConnectionPolicy(backoff=_NO_DELAY)))

    async with transport as transport:
        await transport.aconnect()
        consumer = asyncio.create_task(_drain(transport))

        await asyncio.sleep(0.05)
        await transport.asend(messages.HeartbeatEvent())
        await asyncio.sleep(0.005)
        first.drop()
        await asyncio.sleep(0.2)

        # The queue must be drainable again on the new connection.
        await asyncio.wait_for(transport.aflush(), timeout=1.0)

        await transport.adisconnect()
        await _stop(consumer)
