from typing import List, Protocol, runtime_checkable

from rekuest_next import messages
from rekuest_next.protocols import AnyState


@runtime_checkable
class StateSink(Protocol):
    # --- INITIALIZATION & SESSION MANAGEMENT ---
    async def ainitialize(self):
        """Should be called once to set up the sink (e.g., create tables, indexes)."""
        ...

    async def ateardown(self):
        """Cleans up resources, such as database connections."""
        ...

    async def acreate_session(self, states: List[AnyState], implementations: list) -> str:
        """Creates a new session and returns its ID."""
        ...

    # --- WRITE METHODS ---
    async def adump_snapshot(self, snapshot: messages.StateSnapshotEvent):
        """Store a full snapshot of all states at a given revision."""
        ...

    async def awrite_patch(self, patch: messages.StatePatchEvent):
        """Write a single patch event to the store."""
        ...

    async def is_cought_up_to(self, revision: int) -> bool:
        """Returns True if the sink has received all events up to at least the given revision."""
        ...
