import asyncio
import aiosqlite
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Any

from rekuest_next.api.schema import ImplementationInput
from rekuest_next.messages import JSONSerializable
from rekuest_next.agents.sink.protocol import (
    WriteSnapshotReq,
    WritePatchReq,
    AnyState,
)


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

    async def processing_loop(self):
        """Background task to process the queue and write to the database."""
        while True:
            item_type, req = await self.queue.get()
            try:
                if item_type == "snapshot":
                    await self._adump_snapshot(req)
                elif item_type == "patch":
                    await self._awrite_patch(req)
                else:
                    raise ValueError(f"Unknown item type in queue: {item_type}")
            except Exception as e:
                print(f"Error processing {item_type}: {e}")
            finally:
                self.queue.task_done()

    # --- INITIALIZATION & SESSION MANAGEMENT ---
    async def ainitialize(self):
        self.loop = asyncio.get_event_loop()
        self.queue = asyncio.Queue()
        self.processing_loop_task = self.loop.create_task(self.processing_loop())

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

            await db.commit()

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

    def dump_snapshot(self, req: WriteSnapshotReq):
        self.loop.call_soon_threadsafe(lambda: self.queue.put_nowait(("snapshot", req)))

    def write_patch(self, req: WritePatchReq):
        self.loop.call_soon_threadsafe(lambda: self.queue.put_nowait(("patch", req)))

    # --- WRITE METHODS ---
    async def _adump_snapshot(self, req: WriteSnapshotReq):
        target_session = req.session_id or self.current_session_id
        epoch_ms = dt_to_epoch_ms(req.event_time)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO state_snapshots (state_id, revision, event_time, session_id, state_data) 
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    req.state_id,
                    req.revision,
                    epoch_ms,
                    target_session,
                    json.dumps(req.state_data),
                ),
            )
            await db.commit()

    async def _awrite_patch(self, req: WritePatchReq):
        if req.future_rev != req.current_rev + 1:
            raise ValueError(
                f"Integrity Error: future_rev ({req.future_rev}) must be exactly "
                f"current_rev ({req.current_rev}) + 1."
            )

        target_session = req.session_id or self.current_session_id
        epoch_ms = dt_to_epoch_ms(req.event_time)

        # We dump the value to a JSON string. If the op is "remove", value might be None.
        value_as_json = json.dumps(req.value) if req.value != None else None

        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    """
                    INSERT INTO state_patches (
                        state_id, current_rev, future_rev, event_time, 
                        correlation_id, session_id, op, path, value
                    ) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        req.state_id,
                        req.current_rev,
                        req.future_rev,
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
        self.processing_loop_task.cancel()
        try:
            await self.processing_loop_task
        except asyncio.CancelledError:
            pass

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
