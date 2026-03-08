import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from rekuest_next.api.schema import ImplementationInput
from rekuest_next.protocols import AnyState

from .protocol import (
    WritePatchReq,
    WriteSnapshotReq,
)


@dataclass
class MemoryStore:
    patches: List[WritePatchReq] = field(default_factory=lambda: [])
    snapshots: List[WriteSnapshotReq] = field(default_factory=lambda: [])


class MemorySink:
    # --- INITIALIZATION & SESSION MANAGEMENT ---

    def __init__(self, memory: Optional[MemoryStore] = None):
        """Initializes the MemorySink with the path to the SQLite database file. The sink will use this database to store snapshots and patches in memory. If the file does not exist, it will be created automatically."""
        self.store = memory or MemoryStore()

    async def ainitialize(self):
        """Should be called once to set up the sink (e.g., create tables, indexes)."""
        return None

    async def ateardown(self):
        """Cleans up resources, such as database connections."""
        return None

    async def acreate_session(
        self, states: List[AnyState], implementations: List[ImplementationInput]
    ) -> str:
        """Creates a new session and returns its ID. Should be called at the start of a new logical session.

        By default this will be called automatically on each agent startup, but can be called manually if the agent wants to manage sessions itself (e.g., create a new session for each user interaction).

        """
        return str(uuid.uuid4())

    # --- WRITE METHODS ---
    async def adump_snapshot(self, req: WriteSnapshotReq):
        """Will store a full snapshot of the state at a given revision. This is intended to be used for periodic checkpointing to optimize retrieval, but can also be used by agents to manually create snapshots at important milestones (e.g., end of a user interaction)."""
        self.store.snapshots.append(req)

    async def awrite_patch(self, req: WritePatchReq):
        """Writes a patch to the store. The sink should enforce that patches are written in order (i.e., future_rev must be exactly current_rev + 1) to maintain integrity. The correlation_id can be used to group patches that belong to the same logical task or operation, which can be useful for retrieval and debugging."""
        self.store.patches.append(req)

    async def is_cought_up_to(self, state_id: str, revision: int) -> bool:
        """Returns True if the sink has received patches/snapshots up to at least the given revision for the specified state_id. This can be used by agents to check if they are in sync with the latest state before performing operations that depend on up-to-date information."""
        return True
