import copy
from datetime import datetime, timezone
from typing import Optional, cast

import jsonpatch  # type: ignore[import-untyped]

from rekuest_next import messages
from rekuest_next.contrib.fastapi.retriever.protocol import (
    PatchEvent,
    SessionBoundary,
    Snapshot,
    TaskBoundary,
)
from rekuest_next.contrib.fastapi.sink.memory_sink import MemoryStore
from rekuest_next.messages import JSONSerializable


class MemoryRetriever:
    """In-memory retriever for persisted state history stored as transport messages."""

    def __init__(self, store: Optional[MemoryStore] = None) -> None:
        self.store = store

    async def ainitialize(self) -> None:
        return None

    async def ateardown(self) -> None:
        return None

    async def aget_task_boundaries(
        self,
        correlation_id: str,
        state_id: Optional[str] = None,
    ) -> Optional[TaskBoundary]:
        patches = [
            patch
            for patch in self._get_patches()
            if patch.correlation_id == correlation_id
            and (state_id is None or patch.state_name == state_id)
        ]
        if not patches:
            return None

        return TaskBoundary(
            correlation_id=correlation_id,
            start_global_revision=min(patch.global_rev - 1 for patch in patches),
            end_global_revision=max(patch.global_rev for patch in patches),
            start_time=min(
                datetime.fromtimestamp(patch.ts, tz=timezone.utc) for patch in patches
            ),
            end_time=max(
                datetime.fromtimestamp(patch.ts, tz=timezone.utc) for patch in patches
            ),
        )

    async def aget_session_boundaries(
        self, session_id: str, state_id: Optional[str] = None
    ) -> Optional[SessionBoundary]:
        patches = [
            patch
            for patch in self._get_patches()
            if patch.session_id == session_id
            and (state_id is None or patch.state_name == state_id)
        ]
        if not patches:
            return None

        return SessionBoundary(
            session_id=session_id,
            start_global_revision=min(patch.global_rev - 1 for patch in patches),
            end_global_revision=max(patch.global_rev for patch in patches),
            start_time=min(
                datetime.fromtimestamp(patch.ts, tz=timezone.utc) for patch in patches
            ),
            end_time=max(
                datetime.fromtimestamp(patch.ts, tz=timezone.utc) for patch in patches
            ),
        )

    async def aget_state_at_global_rev(
        self,
        global_revision: int,
        state_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Snapshot | list[Snapshot] | None:
        return self._aget_state_at_revision(
            target_revision=global_revision,
            state_id=state_id,
            session_id=session_id,
        )

    async def aget_forward_events_after_rev(
        self,
        global_revision: int,
        state_id: Optional[str] = None,
        session_id: Optional[str] = None,
        count: int = 100,
    ) -> list[PatchEvent]:
        patches = [
            patch
            for patch in self._get_patches()
            if (patch.global_rev - 1) >= global_revision
            and (state_id is None or patch.state_name == state_id)
            and (session_id is None or patch.session_id == session_id)
        ]
        return [
            self._to_patch_event(patch)
            for patch in sorted(
                patches,
                key=lambda item: (item.global_rev - 1, item.state_name),
            )[:count]
        ]

    async def aget_patch_events_between_global_revs(
        self,
        from_global_revision: int,
        to_global_revision: int,
        state_ids: Optional[list[str]] = None,
        session_id: Optional[str] = None,
    ) -> list[PatchEvent]:
        patches = [
            patch
            for patch in self._get_patches()
            if (patch.global_rev - 1) >= from_global_revision
            and patch.global_rev <= to_global_revision
            and (state_ids is None or patch.state_name in state_ids)
            and (session_id is None or patch.session_id == session_id)
        ]
        return [
            self._to_patch_event(patch)
            for patch in sorted(
                patches,
                key=lambda item: (item.global_rev - 1, item.state_name),
            )
        ]

    async def aget_snapshots_around_rev(
        self,
        revision: int,
        state_id: Optional[str] = None,
        session_id: Optional[str] = None,
        before: int = 1,
        after: int = 1,
    ) -> list[Snapshot]:
        state_ids = (
            [state_id] if state_id is not None else self._get_state_ids(session_id)
        )
        collected: list[Snapshot] = []

        for candidate_state_id in state_ids:
            # Build per-state snapshot list from StateSnapshotEvent messages
            state_snapshots = self._extract_state_snapshots(
                candidate_state_id, session_id
            )
            before_snapshots = sorted(
                (s for s in state_snapshots if s[0] <= revision),
                key=lambda item: item[0],
            )[-before:]
            after_snapshots = sorted(
                (s for s in state_snapshots if s[0] > revision),
                key=lambda item: item[0],
            )[:after]
            for rev, data, sess_id in before_snapshots:
                collected.append(
                    Snapshot(
                        timepoint=datetime.now(timezone.utc),
                        data=copy.deepcopy(data),
                        global_revision=rev,
                        session_id=sess_id,
                    )
                )
            for rev, data, sess_id in after_snapshots:
                collected.append(
                    Snapshot(
                        timepoint=datetime.now(timezone.utc),
                        data=copy.deepcopy(data),
                        global_revision=rev,
                        session_id=sess_id,
                    )
                )

        return collected

    def _extract_state_snapshots(
        self,
        state_id: str,
        session_id: Optional[str],
    ) -> list[tuple[int, JSONSerializable, str]]:
        """Extract per-state (global_rev, data, session_id) tuples from stored snapshot events."""
        result: list[tuple[int, JSONSerializable, str]] = []
        for event in self._get_snapshots():
            if session_id is not None and event.session_id != session_id:
                continue
            if state_id in event.snapshots:
                result.append(
                    (event.global_rev, event.snapshots[state_id], event.session_id)
                )
        return result

    def _aget_state_at_revision(
        self,
        target_revision: int,
        state_id: Optional[str],
        session_id: Optional[str],
    ) -> Snapshot | list[Snapshot] | None:
        state_ids = (
            [state_id] if state_id is not None else self._get_state_ids(session_id)
        )
        snapshots = [
            snapshot
            for snapshot in (
                self._build_state_snapshot(
                    candidate_state_id,
                    target_revision=target_revision,
                    session_id=session_id,
                )
                for candidate_state_id in state_ids
            )
            if snapshot is not None
        ]
        if state_id is None:
            return snapshots
        return snapshots[0] if snapshots else None

    def _build_state_snapshot(
        self,
        state_id: str,
        target_revision: int,
        session_id: Optional[str],
    ) -> Optional[Snapshot]:
        # Find best anchor from snapshot events
        state_snapshots = self._extract_state_snapshots(state_id, session_id)
        if not state_snapshots:
            return None

        anchor = max(
            (s for s in state_snapshots if s[0] <= target_revision),
            key=lambda s: s[0],
            default=None,
        )
        if anchor is None:
            return None

        anchor_revision, anchor_data, anchor_session = anchor
        current_state = cast(JSONSerializable, copy.deepcopy(anchor_data))

        patches = [
            patch
            for patch in self._get_patches()
            if patch.state_name == state_id
            and (patch.global_rev - 1) >= anchor_revision
            and patch.global_rev <= target_revision
            and (session_id is None or patch.session_id == session_id)
        ]
        patches = sorted(patches, key=lambda item: item.global_rev - 1)

        last_global_revision = anchor_revision
        last_timepoint = datetime.now(timezone.utc)

        for patch in patches:
            patch_document = self._to_patch_document(patch.op, patch.path, patch.value)
            current_state = cast(
                JSONSerializable,
                jsonpatch.apply_patch(current_state, [patch_document], in_place=False),
            )
            last_global_revision = patch.global_rev
            last_timepoint = datetime.fromtimestamp(patch.ts, tz=timezone.utc)

        return Snapshot(
            timepoint=last_timepoint,
            data=copy.deepcopy(current_state),
            global_revision=last_global_revision,
            session_id=anchor_session,
        )

    def _to_patch_event(self, patch: messages.StatePatchEvent) -> PatchEvent:
        return PatchEvent(
            timepoint=datetime.fromtimestamp(patch.ts, tz=timezone.utc),
            state_id=patch.state_name,
            global_current_rev=patch.global_rev - 1,
            global_future_rev=patch.global_rev,
            correlation_id=patch.correlation_id or "",
            session_id=patch.session_id or "",
            patch=self._to_patch_document(patch.op, patch.path, patch.value),
        )

    def _to_patch_document(
        self, op: str, path: str, value: JSONSerializable | None
    ) -> dict[str, JSONSerializable]:
        patch_document: dict[str, JSONSerializable] = {"op": op, "path": path}
        if op != "remove":
            patch_document["value"] = value
        return patch_document

    def _get_patches(self) -> list[messages.StatePatchEvent]:
        if self.store is None:
            return []
        return list(self.store.patches)

    def _get_snapshots(self) -> list[messages.StateSnapshotEvent]:
        if self.store is None:
            return []
        return list(self.store.snapshots)

    def _get_state_ids(self, session_id: Optional[str]) -> list[str]:
        state_ids: set[str] = set()
        for event in self._get_snapshots():
            if session_id is None or event.session_id == session_id:
                state_ids.update(event.snapshots.keys())
        for patch in self._get_patches():
            if session_id is None or patch.session_id == session_id:
                state_ids.add(patch.state_name)
        return sorted(state_ids)
