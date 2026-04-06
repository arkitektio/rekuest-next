import asyncio
import aiosqlite
import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from rekuest_next import messages
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
    """A sink implementation that uses a SQLite database to store state snapshots and patches. This sink is designed for durability and can be used in production environments where persistence is required. It ensures that patches are written in order and provides methods for checking if the sink is caught up to a certain revision."""

    def __init__(self, db_path: str = "ff.db") -> None:
        """Initializes the SQLLiteSink with the path to the SQLite database file. The sink will use this database to store snapshots and patches. If the file does not exist, it will be created automatically."""
        self.db_path = db_path
        self.current_session_id: Optional[str] = None

    # --- INITIALIZATION & SESSION MANAGEMENT ---
    async def ainitialize(self) -> None:
        """Initializes the SQLLiteSink by creating necessary tables and indexes if they don't exist. This should be called once at the start of the agent's lifecycle."""
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
                    global_revision INTEGER NOT NULL,
                    event_time INTEGER NOT NULL,
                    session_id TEXT NOT NULL,
                    state_data TEXT NOT NULL,
                    PRIMARY KEY (state_id, global_revision, session_id),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                );
            """)

            # Updated with op, path, and value columns replacing patch_data
            await db.execute("""
                CREATE TABLE IF NOT EXISTS state_patches (
                    state_id TEXT NOT NULL,
                    global_current_rev INTEGER NOT NULL,
                    global_future_rev INTEGER NOT NULL,
                    event_time INTEGER NOT NULL,
                    correlation_id TEXT,
                    session_id TEXT NOT NULL,
                    op TEXT NOT NULL,
                    path TEXT NOT NULL,
                    value TEXT,
                    PRIMARY KEY (state_id, global_current_rev, session_id),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
                    CHECK (global_future_rev = global_current_rev + 1) 
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

    async def acreate_session(self, states: List[AnyState], implementations: list) -> str:
        """Create a new session and return its ID. Should be called at the start of a new logical session. By default this will be called automatically on each agent startup, but can also be called manually if the agent wants to manage sessions itself (e.g., create a new session for each user interaction)."""
        new_session = str(uuid.uuid4())
        created_at_ms = dt_to_epoch_ms(datetime.now(timezone.utc))

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO sessions (session_id, created_at) VALUES (?, ?)",
                (new_session, created_at_ms),
            )
            await db.commit()

        self.current_session_id = new_session
        return new_session

    # --- WRITE METHODS ---
    async def adump_snapshot(self, snapshot: messages.StateSnapshotEvent) -> None:
        """Store a full snapshot of all states at a given revision."""
        target_session = snapshot.session_id or self.current_session_id
        epoch_ms = dt_to_epoch_ms(datetime.now(timezone.utc))
        async with self._write_lock:
            async with aiosqlite.connect(self.db_path) as db:
                for state_id, state_data in snapshot.snapshots.items():
                    await db.execute(
                        """
                        INSERT OR IGNORE INTO state_snapshots (
                            state_id, revision, global_revision, event_time, session_id, state_data
                        ) 
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        (
                            state_id,
                            snapshot.global_rev,
                            snapshot.global_rev,
                            epoch_ms,
                            target_session,
                            json.dumps(state_data),
                        ),
                    )
                await db.commit()

    async def awrite_patch(self, patch: messages.StatePatchEvent) -> None:
        """Write a single patch event to the store."""
        global_current_rev = patch.global_rev - 1
        global_future_rev = patch.global_rev

        target_session = patch.session_id or self.current_session_id
        epoch_ms = dt_to_epoch_ms(datetime.fromtimestamp(patch.ts, tz=timezone.utc))

        # We dump the value to a JSON string. If the op is "remove", value might be None.
        value_as_json = json.dumps(patch.value) if patch.value is not None else None

        async with self._write_lock:
            async with aiosqlite.connect(self.db_path) as db:
                try:
                    await db.execute(
                        """
                        INSERT INTO state_patches (
                            state_id, global_current_rev, global_future_rev, event_time, 
                            correlation_id, session_id, op, path, value
                        ) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            patch.state_name,
                            global_current_rev,
                            global_future_rev,
                            epoch_ms,
                            patch.correlation_id,
                            target_session,
                            patch.op,
                            patch.path,
                            value_as_json,
                        ),
                    )
                    await db.commit()
                except aiosqlite.IntegrityError as e:
                    raise RuntimeError(
                        f"Database Integrity Violation on patch {global_current_rev}->{global_future_rev}: {e}"
                    )

    async def ateardown(self):
        """Cleans up resources, such as the background processing task."""
        return None

    async def is_cought_up_to(self, revision: int) -> bool:
        """Returns True if the sink has received patches/snapshots up to at least the given revision for the specified state_id."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT MAX(global_future_rev) FROM state_patches
                """
            ) as cursor:
                row = await cursor.fetchone()
                max_future_rev = row[0] if row and row[0] is not None else 0
                return max_future_rev >= revision
