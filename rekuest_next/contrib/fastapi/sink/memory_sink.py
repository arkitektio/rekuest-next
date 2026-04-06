import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from rekuest_next import messages
from rekuest_next.protocols import AnyState


@dataclass
class MemoryStore:
    patches: List[messages.StatePatchEvent] = field(default_factory=list)
    snapshots: List[messages.StateSnapshotEvent] = field(default_factory=list)


class MemorySink:
    """In-memory sink that stores patches and snapshots as transport messages."""

    def __init__(self, memory: Optional[MemoryStore] = None):
        self.store = memory or MemoryStore()
        self._session_id: Optional[str] = None

    async def ainitialize(self):
        return None

    async def ateardown(self):
        return None

    async def acreate_session(self, states: List[AnyState], implementations: list) -> str:
        self._session_id = str(uuid.uuid4())
        return self._session_id

    async def adump_snapshot(self, snapshot: messages.StateSnapshotEvent):
        self.store.snapshots.append(snapshot)

    async def awrite_patch(self, patch: messages.StatePatchEvent):
        self.store.patches.append(patch)

    async def is_cought_up_to(self, revision: int) -> bool:
        return True
