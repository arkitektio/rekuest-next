from typing import Optional

from rekuest_next.agents.retriever.protocol import (
    TaskBoundary,
    SessionBoundary,
    AroundWindow,
)


class MemoryRetriever:
    """The MemoryRetriever is responsible for fetching historical state data (snapshots and patches) from the sink. It provides methods to retrieve the state of an entity at a specific revision, as well as to fetch a window of changes around a target revision. This allows agents to reconstruct the state of an entity at any point in time, which is essential for making informed decisions based on past events and changes."""

    async def ainitialize(self):
        """Should be called once to set up the sink (e.g., create tables, indexes)."""
        return None

    async def ateardown(self):
        """Cleans up resources, such as database connections."""
        return None

    async def aget_task_boundaries(
        self,
        correlation_id: str,
        state_id: Optional[str] = None,
    ) -> Optional[TaskBoundary]:
        """Given a state_id and a correlation_id, returns the start and end revisions and timestamps for that task. This allows agents to query the history of a specific operation or task, which can be useful for debugging, auditing, or reconstructing the sequence of events that led to a particular state."""
        raise NotImplementedError(
            "MemoryRetriever is a stub and does not have access to historical data. The get_task_boundaries method is not implemented for MemoryRetriever yet."
        )

    async def aget_session_boundaries(
        self, session_id: str, state_id: Optional[str] = None
    ) -> Optional[SessionBoundary]:
        raise NotImplementedError(
            "MemoryRetriever is a stub and does not have access to historical data. The get_session_boundaries method is not implemented for MemoryRetriever yet."
        )

    async def aget_around_window(
        self,
        state_id: str,
        target_revision: int,
        radius_before: int,
        radius_after: int,
    ) -> Optional[AroundWindow]:
        raise NotImplementedError(
            "MemoryRetriever is a stub and does not have access to historical data. The get_around_window method is not implemented for MemoryRetriever yet."
        )
