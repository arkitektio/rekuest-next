"""A control plane backed by a local :class:`StateSink`.

The in-process FastAPI agent has no server to register with; what it does have is a sink
that owns sessions. This is that difference expressed as a backend rather than as
``BaseAgent`` overrides.
"""

from typing import TYPE_CHECKING, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from rekuest_next.contrib.fastapi.sink.protocol import StateSink
from rekuest_next.protocols import AnyState
from rekuest_next.scalars import Identifier

if TYPE_CHECKING:
    from rekuest_next.app import AppRegistry


class SinkAgentBackend(BaseModel):
    """Mints sessions through a sink; nothing to register, nothing to shelve."""

    sink: StateSink = Field(description="The sink that owns sessions for this agent.")
    states: List[AnyState] = Field(
        default_factory=list,
        description="States to record on the session. Refreshed by the agent before the session is created.",
    )
    implementations: List[object] = Field(
        default_factory=list,
        description="Implementations to record on the session.",
    )
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def registered_agent_id(self) -> Optional[str]:
        """The in-process agent is not assigned an id by anyone."""
        return None

    async def aensure_registered(
        self,
        app_registry: "AppRegistry",
        name: Optional[str],
        definition_hash: str,
    ) -> None:
        """Nothing to register: the definitions never leave this process.

        The session created below carries them instead, so they are recorded here.
        """
        self.implementations = list(app_registry.implementations.values())
        return None

    async def acreate_session(self) -> str:
        """Ask the sink for a session id, recording what this agent implements."""
        return await self.sink.acreate_session(
            states=self.states,
            implementations=self.implementations,
        )

    async def ashelve(
        self,
        identifier: Identifier,
        resource_id: str,
        label: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        """Not supported for the in-process agent."""
        raise NotImplementedError("Shelving is not implemented for FastApiAgent yet.")

    async def acollect(self, key: str) -> None:
        """Not supported for the in-process agent."""
        raise NotImplementedError("Shelving is not implemented for FastApiAgent yet.")
