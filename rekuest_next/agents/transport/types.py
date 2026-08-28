"""The contract between an agent and its transport.

A transport owns the *connection*: opening it, authenticating, retrying, and serialising
in both directions. The agent above it owns *session semantics* — what the messages mean.
The things the connection layer cannot know on its own — which token to present, which
process it is presenting it for, how hard to fight to stay connected, and who to tell
when that changes — are handed to it by the agent through the :class:`TransportHost` it
installs.

This module is the canonical statement of that contract.
:class:`rekuest_next.agents.transport.base.AgentTransport` is the base class transports
inherit to get the fields and default behaviour; the two must stay in step.
"""

from types import TracebackType
from typing import Protocol, runtime_checkable
from collections.abc import AsyncIterator

from pydantic import BaseModel, ConfigDict, Field

from rekuest_next.agents.policy import ConnectionPolicy
from rekuest_next.messages import FromAgentMessage, ToAgentMessage


class HandshakeParams(BaseModel):
    """The *agent-owned* half of registering a connection.

    Each layer contributes only what it owns: the transport supplies the credential (it
    holds the token loader and reloads it per attempt), and the agent supplies the
    registration intent below. Requested once per connect *attempt*, so a reconnect
    reflects current agent state rather than whatever was true at build time.
    """

    force: bool | None = Field(default=None)
    """Kick any connection already registered for this agent and take over.

    ``None`` means "no opinion" — the transport keeps its own build-time default. Only
    honoured for participants that execute work; a non-executor never displaces its own
    other connections.
    """
    session_id: str | None = Field(default=None)
    """Per-process identifier, minted in memory by the agent at start-up and never
    persisted. Its volatility is the reclaim signal: reconnecting with the SAME
    session_id means the process survived and in-flight work can be reclaimed; a
    DIFFERENT one means this is a fresh process."""

    model_config = ConfigDict(frozen=True)


@runtime_checkable
class HandshakeProvider(Protocol):
    """Supplies the per-attempt handshake. Implemented by the agent."""

    async def aget_handshake_params(self) -> HandshakeParams:
        """Build the handshake for one connect attempt."""
        ...


@runtime_checkable
class TransportHost(HandshakeProvider, Protocol):
    """Everything the transport needs from the agent above it.

    A superset of :class:`HandshakeProvider`, which it replaces. The transport owns
    the socket, but two decisions about that socket belong to the agent: *how hard
    to fight for it* (the policy below) and *who needs to know when it changes
    state* (the callback below). Both are pushed down here rather than being
    hardcoded in the transport, because only the agent knows what work is riding on
    the connection.
    """

    @property
    def connection_policy(self) -> ConnectionPolicy:
        """The reconnect budget the transport should honour."""
        ...

    async def aon_connection_change(self, healthy: bool) -> None:
        """Called on each transition of the live connection.

        ``True`` once a connection is up and registered, ``False`` when it drops —
        including drops the transport goes on to retry transparently, which is
        precisely the window the agent could not previously see.
        """
        ...


@runtime_checkable
class MessageSink(Protocol):
    """Somewhere to put one outbound message.

    The narrow slice of :class:`AgentTransport` that the agent-as-caller postman needs.
    Depending on this instead of the whole agent is what keeps
    :class:`~rekuest_next.agents.caller.AgentPostman` from reaching two levels down
    through ``agent.transport``.
    """

    @property
    def connected(self) -> bool:
        """Whether messages can currently be sent."""
        ...

    async def asend(self, message: FromAgentMessage) -> None:
        """Send one message."""
        ...


@runtime_checkable
class AgentTransport(MessageSink, Protocol):
    """Protocol for transport."""

    def set_transport_host(self, host: TransportHost) -> None:
        """Install the agent the transport asks for handshake, policy and callbacks.

        Transports without a connection to manage (an in-process queue, say) ignore
        it.
        """
        ...

    async def aconnect(self) -> None:
        """Connect to the transport."""
        ...

    async def adisconnect(self) -> None:
        """Disconnect from the transport."""
        ...

    async def __aenter__(self) -> "AgentTransport":
        """Enter the transport context."""
        ...

    def areceive(self) -> AsyncIterator[ToAgentMessage]:
        """Receive messages from the transport.

        Ends when the connection closes, and raises whatever terminal failure the
        connection hit into the consumer's frame. Typed as ``AsyncIterator`` because that
        is all the agent needs — it only ever calls ``__aiter__`` on the result.
        """
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: "TracebackType | None",
        /,
    ) -> None:
        """Exit the transport context.

        Declared positional-only. Parameter *names* are part of a Protocol signature, and
        the shipped transports spell these differently (``exc_value``/``traceback`` vs
        ``exc_val``/``exc_tb``), so requiring a particular spelling would silently stop
        one of them from satisfying the contract. ``async with`` only ever passes these
        positionally anyway.
        """
        ...
