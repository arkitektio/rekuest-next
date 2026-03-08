import aiosqlite
import json
from datetime import datetime, timezone
from typing import Any, Optional, cast

from rekuest_next.agents.retriever.protocol import (
    PatchEvent,
    SessionBoundary,
    Snapshot,
    TaskBoundary,
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
    async def ainitialize(self) -> None:
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
        return None

    async def aget_state_at_global_rev(
        self,
        global_revision: int,
        state_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Snapshot | list[Snapshot] | None:
        return await self._aget_state_at_revision(
            target_revision=global_revision,
            state_id=state_id,
            session_id=session_id,
            use_global_revision=True,
        )

    async def aget_state_at_local_rev(
        self,
        revision: int,
        state_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Snapshot | list[Snapshot] | None:
        return await self._aget_state_at_revision(
            target_revision=revision,
            state_id=state_id,
            session_id=session_id,
            use_global_revision=False,
        )

    async def aget_forward_events_after_rev(
        self,
        revision: int,
        state_id: Optional[str] = None,
        session_id: Optional[str] = None,
        count: int = 100,
    ) -> list[PatchEvent]:
        session_filter = "AND session_id = ?" if session_id is not None else ""
        state_filter = "AND state_id = ?" if state_id is not None else ""
        params: tuple[object, ...] = (revision, count)
        if state_id is not None and session_id is not None:
            params = (revision, state_id, session_id, count)
        elif state_id is not None:
            params = (revision, state_id, count)
        elif session_id is not None:
            params = (revision, session_id, count)

        query = f"""
        SELECT current_rev, future_rev, global_current_rev, global_future_rev,
               event_time, correlation_id, session_id, op, path, value
        FROM state_patches
        WHERE current_rev >= ? {state_filter} {session_filter}
        ORDER BY current_rev ASC, state_id ASC
        LIMIT ?
        """

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()

        return [self._row_to_patch_event(row) for row in rows]

    async def aget_snapshots_around_rev(
        self,
        revision: int,
        state_id: Optional[str] = None,
        session_id: Optional[str] = None,
        before: int = 1,
        after: int = 1,
    ) -> list[Snapshot]:
        state_ids = [state_id] if state_id is not None else await self._aget_state_ids(session_id)
        collected: list[Snapshot] = []

        for candidate_state_id in state_ids:
            before_query = """
        SELECT revision, global_revision, event_time, session_id, state_data
        FROM state_snapshots
        WHERE state_id = ? AND revision <= ? {session_filter}
        ORDER BY revision DESC
        LIMIT ?
        """
            after_query = """
        SELECT revision, global_revision, event_time, session_id, state_data
        FROM state_snapshots
        WHERE state_id = ? AND revision > ? {session_filter}
        ORDER BY revision ASC
        LIMIT ?
        """
            session_filter = "AND session_id = ?" if session_id is not None else ""
            before_params: tuple[object, ...] = (candidate_state_id, revision, before)
            after_params: tuple[object, ...] = (candidate_state_id, revision, after)
            if session_id is not None:
                before_params = (candidate_state_id, revision, session_id, before)
                after_params = (candidate_state_id, revision, session_id, after)

            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    before_query.format(session_filter=session_filter), before_params
                ) as cursor:
                    before_rows = await cursor.fetchall()
                async with db.execute(
                    after_query.format(session_filter=session_filter), after_params
                ) as cursor:
                    after_rows = await cursor.fetchall()

            collected.extend(
                self._row_to_snapshot(row) for row in [*reversed(before_rows), *after_rows]
            )

        return collected

    async def _aget_state_at_revision(
        self,
        target_revision: int,
        state_id: Optional[str],
        session_id: Optional[str],
        use_global_revision: bool,
    ) -> Snapshot | list[Snapshot] | None:
        if state_id is None:
            state_ids = await self._aget_state_ids(session_id)
            snapshots = [
                snapshot
                for snapshot in [
                    await self._aget_state_at_revision(
                        target_revision=target_revision,
                        state_id=candidate_state_id,
                        session_id=session_id,
                        use_global_revision=use_global_revision,
                    )
                    for candidate_state_id in state_ids
                ]
                if isinstance(snapshot, Snapshot)
            ]
            return snapshots

        snapshot_revision_column = "global_revision" if use_global_revision else "revision"
        patch_current_column = "global_current_rev" if use_global_revision else "current_rev"
        patch_future_column = "global_future_rev" if use_global_revision else "future_rev"
        session_filter = "AND session_id = ?" if session_id is not None else ""

        anchor_query = f"""
        SELECT revision, global_revision, event_time, session_id, state_data
        FROM state_snapshots
        WHERE state_id = ? AND {snapshot_revision_column} <= ? {session_filter}
        ORDER BY {snapshot_revision_column} DESC
        LIMIT 1
        """
        patch_query = f"""
        SELECT current_rev, future_rev, global_current_rev, global_future_rev,
               event_time, correlation_id, session_id, op, path, value
        FROM state_patches
        WHERE state_id = ? AND {patch_current_column} >= ? AND {patch_future_column} <= ? {session_filter}
        ORDER BY {patch_current_column} ASC
        """

        anchor_params: tuple[object, ...] = (state_id, target_revision)
        patch_start_revision = 0
        if session_id is not None:
            anchor_params = (state_id, target_revision, session_id)

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(anchor_query, anchor_params) as cursor:
                anchor_row = await cursor.fetchone()

            if anchor_row is None:
                return None

            anchor_snapshot = self._row_to_snapshot(anchor_row)
            patch_start_revision = (
                anchor_snapshot.global_revision if use_global_revision else anchor_snapshot.revision
            ) or 0

            patch_params: tuple[object, ...] = (state_id, patch_start_revision, target_revision)
            if session_id is not None:
                patch_params = (state_id, patch_start_revision, target_revision, session_id)

            async with db.execute(patch_query, patch_params) as cursor:
                patch_rows = await cursor.fetchall()

        state_data = cast(JSONSerializable, json.loads(json.dumps(anchor_snapshot.data)))
        last_snapshot = anchor_snapshot
        for row in patch_rows:
            patch_event = self._row_to_patch_event(row)
            state_data = self._apply_patch_document(state_data, patch_event.patch)
            last_snapshot = Snapshot(
                timepoint=patch_event.timepoint,
                data=state_data,
                revision=patch_event.future_rev,
                global_revision=patch_event.global_future_rev,
                session_id=patch_event.session_id,
            )

        return last_snapshot

    async def _aget_state_ids(self, session_id: Optional[str]) -> list[str]:
        session_filter = "WHERE session_id = ?" if session_id is not None else ""
        params: tuple[object, ...] = (session_id,) if session_id is not None else ()

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                f"SELECT DISTINCT state_id FROM state_snapshots {session_filter}", params
            ) as cursor:
                snapshot_state_ids = [row[0] for row in await cursor.fetchall()]
            async with db.execute(
                f"SELECT DISTINCT state_id FROM state_patches {session_filter}", params
            ) as cursor:
                patch_state_ids = [row[0] for row in await cursor.fetchall()]

        return sorted(set(snapshot_state_ids).union(patch_state_ids))

    def _apply_patch_document(
        self,
        state_data: JSONSerializable,
        patch_document: JSONSerializable,
    ) -> JSONSerializable:
        import jsonpatch  # type: ignore[import-untyped]

        return cast(
            JSONSerializable,
            jsonpatch.apply_patch(state_data, [patch_document], in_place=False),
        )

    def _row_to_snapshot(self, row: tuple[Any, ...]) -> Snapshot:
        revision, global_revision, event_time, session_id, state_data = row
        return Snapshot(
            timepoint=epoch_ms_to_dt(event_time),
            data=json.loads(state_data),
            revision=revision,
            global_revision=global_revision,
            session_id=session_id,
        )

    def _row_to_patch_event(self, row: tuple[Any, ...]) -> PatchEvent:
        (
            current_rev,
            future_rev,
            global_current_rev,
            global_future_rev,
            event_time,
            correlation_id,
            session_id,
            op,
            path,
            value,
        ) = row
        patch_document: dict[str, JSONSerializable] = {"op": op, "path": path}
        if op != "remove":
            patch_document["value"] = json.loads(value) if value is not None else None

        return PatchEvent(
            timepoint=epoch_ms_to_dt(event_time),
            current_rev=current_rev,
            future_rev=future_rev,
            global_current_rev=global_current_rev,
            global_future_rev=global_future_rev,
            correlation_id=correlation_id or "",
            session_id=session_id,
            patch=patch_document,
        )

    async def ateardown(self) -> None:
        """Cleans up resources, such as database connections."""
        return None
