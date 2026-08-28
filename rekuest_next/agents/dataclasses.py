"""Plain data containers the agent moves around.

Kept apart from :mod:`rekuest_next.agents.types` (protocols and type variables)
and from the agent's behaviour so that each can be imported without the other.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from rekuest_next.state.publish import Patch
from rekuest_next.structures.types import JSONSerializable


@dataclass
class QueuedPatchEvent:
    """A state patch waiting in the agent's patch queue."""

    interface: str
    patch: Patch
    event_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RevisedState:
    """Current agent-owned shrunk state together with its local revision."""

    revision: int
    data: JSONSerializable


__all__ = ["QueuedPatchEvent", "RevisedState"]
