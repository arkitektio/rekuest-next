import asyncio
import aiosqlite
import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from rekuest_next.api.schema import ImplementationInput
from rekuest_next.agents.sink.protocol import (
    WriteSnapshotReq,
    WritePatchReq,
)
from rekuest_next.protocols import AnyState


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
class SQLLiteSink:
    def __init__(self, db_path: str = "ff.db"):
        self.db_path = db_path
        self.current_session_id: Optional[str] = None

    # --- INITIALIZATION & SESSION MANAGEMENT ---
    async def ainitialize(self):
        self._write_lock = asyncio.Lock()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at INTEGER NOT NULL
                );
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS state_snapshots (
                    state_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    global_revision INTEGER NOT NULL,
                    event_time INTEGER NOT NULL,
                    session_id TEXT NOT NULL,
                    state_data TEXT NOT NULL,
                    PRIMARY KEY (state_id, revision, session_id),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                );
            """)

            # Updated with op, path, and value columns replacing patch_data
            await db.execute("""
                CREATE TABLE IF NOT EXISTS state_patches (
                    state_id TEXT NOT NULL,
                    current_rev INTEGER NOT NULL,
                    future_rev INTEGER NOT NULL,
                    global_current_rev INTEGER NOT NULL,
                    global_future_rev INTEGER NOT NULL,
                    event_time INTEGER NOT NULL,
                    correlation_id TEXT,
                    session_id TEXT NOT NULL,
                    op TEXT NOT NULL,
                    path TEXT NOT NULL,
                    value TEXT,
                    PRIMARY KEY (state_id, current_rev, session_id),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
                    CHECK (future_rev = current_rev + 1) 
                );
            """)

            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_patches_state_time ON state_patches(state_id, event_time);"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshots_state_time ON state_snapshots(state_id, event_time);"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_patches_correlation ON state_patches(state_id, correlation_id);"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_patches_session ON state_patches(state_id, session_id);"
            )

            await self._aensure_column(
                db,
                table_name="state_snapshots",
                column_name="global_revision",
                column_definition="INTEGER NOT NULL DEFAULT 0",
            )
            await self._aensure_column(
                db,
                table_name="state_patches",
                column_name="global_current_rev",
                column_definition="INTEGER NOT NULL DEFAULT 0",
            )
            await self._aensure_column(
                db,
                table_name="state_patches",
                column_name="global_future_rev",
                column_definition="INTEGER NOT NULL DEFAULT 0",
            )

            await db.commit()

    async def _aensure_column(
        self,
        db: aiosqlite.Connection,
        table_name: str,
        column_name: str,
        column_definition: str,
    ) -> None:
        async with db.execute(f"PRAGMA table_info({table_name})") as cursor:
            existing_columns = [row[1] for row in await cursor.fetchall()]

        if column_name not in existing_columns:
            await db.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            )

    async def acreate_session(
        self, states: List[AnyState], implementations: List[ImplementationInput]
    ) -> str:
        new_session = str(uuid.uuid4())
        created_at_ms = dt_to_epoch_ms(datetime.now(timezone.utc))
        print(f"Creating new session: {new_session} at {created_at_ms} ms")

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO sessions (session_id, created_at) VALUES (?, ?)",
                (new_session, created_at_ms),
            )
            await db.commit()

        self.current_session_id = new_session
        return new_session

    # --- WRITE METHODS ---
    async def adump_snapshot(self, req: WriteSnapshotReq):
        target_session = req.session_id or self.current_session_id
        epoch_ms = dt_to_epoch_ms(req.event_time)
        async with self._write_lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT OR IGNORE INTO state_snapshots (
                        state_id, revision, global_revision, event_time, session_id, state_data
                    ) 
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        req.state_id,
                        req.revision,
                        req.global_revision,
                        epoch_ms,
                        target_session,
                        json.dumps(req.state_data),
                    ),
                )
                await db.commit()

    async def awrite_patch(self, req: WritePatchReq):
        if req.future_rev != req.current_rev + 1:
            raise ValueError(
                f"Integrity Error: future_rev ({req.future_rev}) must be exactly "
                f"current_rev ({req.current_rev}) + 1."
            )

        target_session = req.session_id or self.current_session_id
        epoch_ms = dt_to_epoch_ms(req.event_time)

        # We dump the value to a JSON string. If the op is "remove", value might be None.
        value_as_json = json.dumps(req.value) if req.value is not None else None

        async with self._write_lock:
            async with aiosqlite.connect(self.db_path) as db:
                try:
                    await db.execute(
                        """
                        INSERT INTO state_patches (
                            state_id, current_rev, future_rev, global_current_rev, global_future_rev, event_time, 
                            correlation_id, session_id, op, path, value
                        ) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            req.state_id,
                            req.current_rev,
                            req.future_rev,
                            req.global_current_rev,
                            req.global_future_rev,
                            epoch_ms,
                            req.correlation_id,
                            target_session,
                            req.op,
                            req.path,
                            value_as_json,
                        ),
                    )
                    await db.commit()
                except aiosqlite.IntegrityError as e:
                    raise RuntimeError(
                        f"Database Integrity Violation on patch {req.current_rev}->{req.future_rev}: {e}"
                    )

    async def ateardown(self):
        """Cleans up resources, such as the background processing task."""
        return None

    async def is_cought_up_to(self, state_id: str, revision: int) -> bool:
        """Returns True if the sink has received patches/snapshots up to at least the given revision for the specified state_id."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT MAX(future_rev) FROM state_patches WHERE state_id = ?
                """,
                (state_id,),
            ) as cursor:
                row = await cursor.fetchone()
                max_future_rev = row[0] if row and row[0] is not None else 0
                return max_future_rev >= revision
