"""The agent's control plane: registration, sessions, and the shelve.

An agent talks to its backend over two quite different channels. The *data plane* is the
message socket, owned by an
:class:`~rekuest_next.agents.transport.types.AgentTransport`. The *control plane* — telling
the backend what this agent implements, minting a session, and putting values on a remote
shelve — does not go over that socket at all: against a real Rekuest server it is GraphQL
over rath, and against the in-process FastAPI agent it is a local sink.

That difference used to be expressed by *subclassing the agent*, which is why swapping
deployments meant overriding a handful of unrelated ``BaseAgent`` methods. Here it is a
collaborator instead, so the agent has one implementation and the deployment picks a
backend.
"""

import logging
import uuid
from typing import TYPE_CHECKING, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from rekuest_next.api.schema import (
    Agent as AgentModel,
    aensure_agent,
    aimplement_agent,
    ashelve,
    aunshelve,
)
from rekuest_next.rath import RekuestNextRath
from rekuest_next.scalars import Identifier

if TYPE_CHECKING:
    from rekuest_next.app import AppRegistry

logger = logging.getLogger(__name__)


@runtime_checkable
class AgentBackend(Protocol):
    """Where an agent registers itself, mints sessions, and shelves values.

    Everything here is *off* the message socket. Implementations are free to be remote
    (GraphQL) or entirely local.
    """

    @property
    def registered_agent_id(self) -> Optional[str]:
        """The id the backend assigned this agent, once registered.

        ``None`` before registration, and for backends that assign none.
        """
        ...

    async def aensure_registered(
        self,
        app_registry: "AppRegistry",
        name: Optional[str],
        definition_hash: str,
    ) -> None:
        """Make sure the backend knows what this agent implements.

        ``definition_hash`` is stable for an unchanged definition, so an implementation
        may skip the work when it matches what the backend already stored.
        """
        ...

    async def acreate_session(self) -> str:
        """Mint an identifier for this run of the process."""
        ...

    async def ashelve(
        self,
        identifier: Identifier,
        resource_id: str,
        label: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        """Put a value on the shelve and return its drawer key."""
        ...

    async def acollect(self, key: str) -> None:
        """Release a drawer the backend previously handed out."""
        ...


class LocalAgentBackend(BaseModel):
    """A backend with nothing behind it.

    Registration is a no-op and sessions are local UUIDs, which is right for an agent
    whose definitions never leave the process. Shelving genuinely needs somewhere to put
    things, so it stays unsupported rather than silently dropping values.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def registered_agent_id(self) -> Optional[str]:
        """No backend, so no assigned id."""
        return None

    async def aensure_registered(
        self,
        app_registry: "AppRegistry",
        name: Optional[str],
        definition_hash: str,
    ) -> None:
        """Nothing to register against."""
        return None

    async def acreate_session(self) -> str:
        """A fresh identifier per process."""
        return str(uuid.uuid4())

    async def ashelve(
        self,
        identifier: Identifier,
        resource_id: str,
        label: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        """Not supported: there is no shelve to put anything on."""
        raise NotImplementedError(
            "This agent has no shelve. Give it a backend that provides one "
            "(e.g. RathAgentBackend) to shelve values."
        )

    async def acollect(self, key: str) -> None:
        """Not supported: nothing was ever shelved remotely."""
        raise NotImplementedError(
            "This agent has no shelve, so there is nothing to collect."
        )


class RathAgentBackend(BaseModel):
    """The control plane of a real Rekuest server, reached over GraphQL."""

    rath: RekuestNextRath = Field(
        description="The graph client used for registration and shelving.",
    )
    model_config = ConfigDict(arbitrary_types_allowed=True)

    _agent: Optional[AgentModel] = None

    @property
    def registered_agent_id(self) -> Optional[str]:
        """The server-assigned agent id, available once registration has run."""
        return self._agent.id if self._agent is not None else None

    async def aensure_registered(
        self,
        app_registry: "AppRegistry",
        name: Optional[str],
        definition_hash: str,
    ) -> None:
        """Register this agent's implementations and states, if they changed.

        The backend stores whatever hash we send and returns it, so a matching hash means
        the definition is unchanged and the whole registration can be skipped.
        """
        agent = await aensure_agent(name=name, rath=self.rath)
        self._agent = agent

        if agent.hash == definition_hash:
            return None

        logger.info(
            "Agent hash does not match, registering implementations and states again"
        )
        # Assembling the input runs its model validators.
        agent_input = app_registry.to_implement_agent_input(name=name)
        implemented = await aimplement_agent(
            name=agent_input.name,
            implementations=agent_input.implementations,
            states=agent_input.states,
            locks=agent_input.locks,
            bloks=agent_input.bloks,
            hash=definition_hash,
            rath=self.rath,
        )
        self._agent = implemented
        logger.info(
            "Registered agent with id %s and hash %s", implemented.id, implemented.hash
        )
        return None

    async def acreate_session(self) -> str:
        """A fresh identifier per process; sessions are not persisted server-side."""
        return str(uuid.uuid4())

    async def ashelve(
        self,
        identifier: Identifier,
        resource_id: str,
        label: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        """Put a value on the server-side shelve and return its drawer id."""
        drawer = await ashelve(
            identifier=identifier,
            resource_id=resource_id,
            label=label,
            description=description,
            rath=self.rath,
        )
        return drawer.id

    async def acollect(self, key: str) -> None:
        """Release a drawer on the server."""
        await aunshelve(id=key, rath=self.rath)
