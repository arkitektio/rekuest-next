import asyncio
import aiosqlite
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from rekuest_next.agents.retriever.protocol import (
    TaskBoundary,
    SessionBoundary,
    AroundWindow,
    PatchEvent,
    Snapshot,
)
from rekuest_next.messages import JSONSerializable


# ==========================================
# 2. Helpers
# ==========================================
def dt_to_epoch_ms(dt: datetime) -> int:
    """Converts a timezone-aware datetime to epoch milliseconds."""
    return int(dt.timestamp() * 1000)


def epoch_ms_to_dt(ms: int) -> datetime:
    """Converts epoch milliseconds back to a timezone-aware datetime."""
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)


# ==========================================
# 3. The Unified Store Class
# ==========================================
class SQLLiteRetriever:
    def __init__(self, db_path: str = "ff.db"):
        self.db_path = db_path
        self.current_session_id: Optional[str] = None

    # --- INITIALIZATION & SESSION MANAGEMENT ---
    async def ainitialize(self):
        return None

    # --- READ / RETRIEVE METHODS ---
    async def aget_task_boundaries(
        self,
        correlation_id: str,
        state_id: str | None = None,
    ) -> Optional[TaskBoundary]:
        # Using strict parameterization for safety
        if state_id is None:
            query = """
            SELECT MIN(current_rev), MAX(future_rev), MIN(event_time), MAX(event_time)
            FROM state_patches
            WHERE correlation_id = ?;
            """
            params = (correlation_id,)
        else:
            query = """
            SELECT MIN(current_rev), MAX(future_rev), MIN(event_time), MAX(event_time)
            FROM state_patches
            WHERE state_id = ? AND correlation_id = ?;
            """
            params = (state_id, correlation_id)

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(query, params) as cursor:
                row = await cursor.fetchone()

        if row and row[0] is not None:
            return TaskBoundary(
                correlation_id=correlation_id,
                start_revision=row[0],
                end_revision=row[1],
                start_time=epoch_ms_to_dt(row[2]),
                end_time=epoch_ms_to_dt(row[3]),
            )
        return None

    async def aget_session_boundaries(
        self, session_id: str, state_id: str | None = None
    ) -> Optional[SessionBoundary]:
        # Completely eliminating f-strings for SQL structural queries to prevent injection
        if state_id is None:
            query = """
            SELECT MIN(current_rev), MAX(future_rev), MIN(event_time), MAX(event_time)
            FROM state_patches
            WHERE session_id = ?;
            """
            params = (session_id,)
        else:
            query = """
            SELECT MIN(current_rev), MAX(future_rev), MIN(event_time), MAX(event_time)
            FROM state_patches
            WHERE session_id = ? AND state_id = ?;
            """
            params = (session_id, state_id)

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(query, params) as cursor:
                row = await cursor.fetchone()

        if row and row[0] is not None:
            return SessionBoundary(
                session_id=session_id,
                start_revision=row[0],
                end_revision=row[1],
                start_time=epoch_ms_to_dt(row[2]),
                end_time=epoch_ms_to_dt(row[3]),
            )
        raise ValueError(
            f"No patches found for session_id={session_id} and state_id={state_id}"
        )

    async def aget_around_window(
        self,
        state_id: str,
        target_revision: int,
        session_id: Optional[str],
        radius_before: int = 100,
        radius_after: int = 100,
    ) -> Optional[AroundWindow]:
        start_rev = max(0, target_revision - radius_before)
        end_rev = target_revision + radius_after

        # SQLite natively handles our new op, path, value using a CASE statement.
        # json_set creates/replaces, json_remove deletes. json(p.value) forces SQLite to treat it as valid JSON.
        recursive_patch_query = """
        WITH RECURSIVE
        anchor_snapshot AS (
            SELECT 
                state_id, 
                revision AS current_rev, 
                revision AS future_rev, 
                event_time, 
                session_id AS entry_session_id,
                state_data,     
                NULL AS op,
                NULL AS path,
                NULL AS value,
                NULL AS correlation_id
            FROM state_snapshots
            WHERE state_id = ? AND revision <= ?
            ORDER BY revision DESC 
            LIMIT 1
        ),
        state_builder(state_id, current_rev, future_rev, event_time, entry_session_id, current_state, op, path, value, correlation_id) AS (
            SELECT state_id, current_rev, future_rev, event_time, entry_session_id, state_data, op, path, value, correlation_id
            FROM anchor_snapshot

            UNION ALL

            SELECT 
                p.state_id, 
                p.current_rev, 
                p.future_rev, 
                p.event_time, 
                p.session_id,
                CASE p.op
                    WHEN 'remove' THEN json_remove(sb.current_state, p.path)
                    ELSE json_set(sb.current_state, p.path, json(p.value))
                END,
                p.op,
                p.path,
                p.value,
                p.correlation_id
            FROM state_builder sb
            JOIN state_patches p ON p.state_id = sb.state_id AND p.current_rev = sb.future_rev
            WHERE p.current_rev < ?
        )
        SELECT current_rev, future_rev, event_time, entry_session_id, op, path, value, correlation_id, current_state
        FROM state_builder
        ORDER BY future_rev ASC;
        """

        snapshot_query = """
        SELECT revision, event_time, session_id, state_data 
        FROM state_snapshots 
        WHERE state_id = ? AND revision > ? AND revision < ?
        ORDER BY revision ASC;
        """

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                recursive_patch_query, (state_id, start_rev, end_rev)
            ) as cursor:
                patch_rows = await cursor.fetchall()

            if not patch_rows:
                raise ValueError(
                    f"No patches found for state_id={state_id} in the revision range {start_rev} to {end_rev}"
                )

            async with db.execute(
                snapshot_query, (state_id, start_rev, end_rev)
            ) as cursor:
                snap_rows = await cursor.fetchall()

            latest_state_before_window = None
            latest_rev_before_window = 0
            latest_time_before_window_ms = 0
            latest_session_before_window = ""

            end_state_data = None
            end_revision = 0
            end_time_ms = 0
            end_session = ""

            intermediate_patches: List[PatchEvent] = []

            for row in patch_rows:
                (
                    curr_rev,
                    fut_rev,
                    evt_time_ms,
                    sess_id,
                    op,
                    path,
                    value_str,
                    corr_id,
                    state_str,
                ) = row

                state_data = json.loads(state_str)

                end_state_data = state_data
                end_revision = fut_rev
                end_time_ms = evt_time_ms
                end_session = sess_id

                if fut_rev <= start_rev:
                    latest_state_before_window = state_data
                    latest_rev_before_window = fut_rev
                    latest_time_before_window_ms = evt_time_ms
                    latest_session_before_window = sess_id
                else:
                    if op is not None:
                        # Reconstruct the patch dictionary dynamically for the dataclass
                        patch_val = (
                            json.loads(value_str) if value_str is not None else None
                        )
                        patch_dict = {"op": op, "path": path}
                        if op != "remove":
                            patch_dict["value"] = patch_val

                        intermediate_patches.append(
                            PatchEvent(
                                timepoint=epoch_ms_to_dt(evt_time_ms),
                                current_rev=curr_rev,
                                future_rev=fut_rev,
                                correlation_id=corr_id,
                                session_id=sess_id,
                                patch=patch_dict,  # Keeping this generic in case your PatchEvent expects the dict
                            )
                        )

            intermediate_snapshots: List[Snapshot] = []
            for row in snap_rows:
                rev, evt_time_ms, sess_id, state_str = row
                intermediate_snapshots.append(
                    Snapshot(
                        timepoint=epoch_ms_to_dt(evt_time_ms),
                        revision=rev,
                        session_id=sess_id,
                        data=json.loads(state_str),
                    )
                )

        initial_snapshot = Snapshot(
            timepoint=epoch_ms_to_dt(latest_time_before_window_ms),
            data=latest_state_before_window,
            revision=latest_rev_before_window,
            session_id=latest_session_before_window,
        )

        end_snapshot = Snapshot(
            timepoint=epoch_ms_to_dt(end_time_ms),
            data=end_state_data,
            revision=end_revision,
            session_id=end_session,
        )

        return AroundWindow(
            target_revision=target_revision,
            radius_before=radius_before,
            radius_after=radius_after,
            initial_snapshot=initial_snapshot,
            intermediate_snapshots=intermediate_snapshots,
            intermediate_patches=intermediate_patches,
            end_snapshot=end_snapshot,
        )

    async def ateardown(self):
        """Cleans up resources, such as database connections."""
        pass
