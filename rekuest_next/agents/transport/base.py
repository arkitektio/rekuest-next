"""Agent Transport Base Class"""

import logging
import warnings
from abc import abstractmethod
from types import TracebackType
from typing import Self, cast
from collections.abc import AsyncIterator

from pydantic import ConfigDict, PrivateAttr

from rekuest_next.agents.policy import ConnectionPolicy
from rekuest_next.messages import FromAgentMessage, ToAgentMessage
from rekuest_next.agents.transport.types import (
    HandshakeParams,
    HandshakeProvider,
    TransportHost,
)

from koil.composition import KoiledModel

logger = logging.getLogger(__name__)

__all__ = [
    "AgentTransport",
    "HandshakeParams",
    "HandshakeProvider",
    "TransportHost",
]


class AgentTransport(KoiledModel):
    """Agent Transport

    A Transport carries the agent's protocol messages to and from the backend. It owns
    the connection itself — opening it, authenticating, retrying, and serialising in both
    directions — and nothing above it. The agent above it only ever deals in
    :data:`~rekuest_next.messages.ToAgentMessage` /
    :data:`~rekuest_next.messages.FromAgentMessage` model instances.

    The contract is the members below, stated canonically as a Protocol in
    :mod:`rekuest_next.agents.transport.types`:

    ``aconnect``     — open the connection (and keep it open across retries).
    ``areceive``     — an async iterator of inbound messages. It ends when the connection
                       is closed, and raises whatever terminal failure the connection hit
                       (``AgentWasKicked``, ``DefiniteConnectionFail``, …) into the
                       consumer's frame.
    ``asend``        — queue one outbound message.
    ``adisconnect``  — flush what is queued, stop retrying, and close.
    ``connected``    — whether a connection is live right now.
    ``__aenter__`` / ``__aexit__`` — allocate and release the per-connection resources.

    A transport that authenticates gets its credentials from the agent, per connect
    attempt, via the :class:`TransportHost` installed with :meth:`set_transport_host`.
    That host also supplies the reconnect budget the transport should honour and the
    callback it fires as the connection comes and goes.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _host: TransportHost | None = PrivateAttr(default=None)

    def set_transport_host(self, host: TransportHost) -> None:
        """Install the agent this transport serves.

        Called by the agent as it starts. The host is asked for handshake params on
        each connect attempt, consulted for the reconnect budget, and notified as the
        connection comes and goes. A transport with nothing to hand off simply never
        reads it.
        """
        self._host = host

    def set_handshake_provider(self, provider: HandshakeProvider) -> None:
        """Deprecated alias for :meth:`set_transport_host`.

        Kept so that code installing only a handshake provider keeps working; such a
        provider supplies no policy or callback, so the transport falls back to its
        defaults for both.
        """
        warnings.warn(
            "set_handshake_provider is deprecated; use set_transport_host instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._host = cast(TransportHost, provider)

    @property
    def connection_policy(self) -> ConnectionPolicy:
        """The reconnect budget to honour, taken from the host when it offers one."""
        policy = getattr(self._host, "connection_policy", None)
        return policy if isinstance(policy, ConnectionPolicy) else ConnectionPolicy()

    async def anotify_connection_change(self, healthy: bool) -> None:
        """Tell the host the live connection came up or went down.

        Best-effort and never fatal: a host that raises here must not be able to turn
        a recoverable drop into a connection failure.
        """
        callback = getattr(self._host, "aon_connection_change", None)
        if callback is None:
            return
        try:
            await callback(healthy)
        except Exception:  # noqa: BLE001 — a listener must not break the connection
            logger.error("Connection-change listener failed", exc_info=True)

    @property
    def connected(self) -> bool:
        """Whether the transport currently holds a live connection.

        Defaults to ``False`` rather than raising, so that a transport which does not
        track this cannot break a caller merely by being asked. Transports that know
        should override.
        """
        return False

    @abstractmethod
    async def asend(self, message: FromAgentMessage) -> None:
        """Send a message to the agent."""
        raise NotImplementedError("This is an abstract Base Class")

    @abstractmethod
    async def aconnect(self) -> None:
        """Connect to the agent."""
        raise NotImplementedError("This is an abstract Base Class")

    @abstractmethod
    def areceive(self) -> AsyncIterator[ToAgentMessage]:
        """Receive messages from the agent."""
        raise NotImplementedError("This is an abstract Base Class")

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
