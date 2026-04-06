import copy
from typing import Optional, cast

import jsonpatch  # type: ignore[import-untyped]

from rekuest_next.agents.retriever.protocol import (
    PatchEvent,
    SessionBoundary,
    Snapshot,
    TaskBoundary,
)
from rekuest_next.agents.sink.memory_sink import MemoryStore
from rekuest_next.agents.sink.protocol import WritePatchReq, WriteSnapshotReq
from rekuest_next.messages import JSONSerializable


class MemoryRetriever:
    """In-memory retriever for persisted state history."""

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
            and (state_id is None or patch.state_id == state_id)
        ]
        if not patches:
            return None

        return TaskBoundary(
            correlation_id=correlation_id,
            start_global_revision=min(patch.global_current_rev for patch in patches),
            end_global_revision=max(patch.global_future_rev for patch in patches),
            start_time=min(patch.event_time for patch in patches),
            end_time=max(patch.event_time for patch in patches),
        )

    async def aget_session_boundaries(
        self, session_id: str, state_id: Optional[str] = None
    ) -> Optional[SessionBoundary]:
        patches = [
            patch
            for patch in self._get_patches()
            if patch.session_id == session_id and (state_id is None or patch.state_id == state_id)
        ]
        if not patches:
            return None

        return SessionBoundary(
            session_id=session_id,
            start_global_revision=min(patch.global_current_rev for patch in patches),
            end_global_revision=max(patch.global_future_rev for patch in patches),
            start_time=min(patch.event_time for patch in patches),
            end_time=max(patch.event_time for patch in patches),
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

    async def aget_state_at_local_rev(
        self,
        revision: int,
        state_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Snapshot | list[Snapshot] | None:
        return self._aget_state_at_revision(
            target_revision=revision,
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
            if patch.global_current_rev >= global_revision
            and (state_id is None or patch.state_id == state_id)
            and (session_id is None or patch.session_id == session_id)
        ]
        return [
            self._to_patch_event(patch)
            for patch in sorted(
                patches,
                key=lambda item: (item.global_current_rev, item.state_id),
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
            if patch.global_current_rev >= from_global_revision
            and patch.global_future_rev <= to_global_revision
            and (state_ids is None or patch.state_id in state_ids)
            and (session_id is None or patch.session_id == session_id)
        ]
        return [
            self._to_patch_event(patch)
            for patch in sorted(
                patches,
                key=lambda item: (item.global_current_rev, item.state_id),
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
        state_ids = [state_id] if state_id is not None else self._get_state_ids(session_id)
        collected: list[Snapshot] = []

        for candidate_state_id in state_ids:
            snapshots = [
                snapshot
                for snapshot in self._get_snapshots()
                if snapshot.state_id == candidate_state_id
                and (session_id is None or snapshot.session_id == session_id)
            ]
            before_snapshots = sorted(
                (snapshot for snapshot in snapshots if snapshot.global_revision <= revision),
                key=lambda item: item.global_revision,
            )[-before:]
            after_snapshots = sorted(
                (snapshot for snapshot in snapshots if snapshot.global_revision > revision),
                key=lambda item: item.global_revision,
            )[:after]
            collected.extend(self._to_snapshot(snapshot) for snapshot in before_snapshots)
            collected.extend(self._to_snapshot(snapshot) for snapshot in after_snapshots)

        return collected

    def _aget_state_at_revision(
        self,
        target_revision: int,
        state_id: Optional[str],
        session_id: Optional[str],
    ) -> Snapshot | list[Snapshot] | None:
        state_ids = [state_id] if state_id is not None else self._get_state_ids(session_id)
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
        snapshots = [
            snapshot
            for snapshot in self._get_snapshots()
            if snapshot.state_id == state_id
            and (session_id is None or snapshot.session_id == session_id)
        ]
        if not snapshots:
            return None

        anchor = max(
            (snapshot for snapshot in snapshots if snapshot.global_revision <= target_revision),
            key=lambda snapshot: snapshot.global_revision,
            default=None,
        )
        if anchor is None:
            return None

        current_state = cast(JSONSerializable, copy.deepcopy(anchor.state_data))
        anchor_revision = anchor.global_revision
        patches = [
            patch
            for patch in self._get_patches()
            if patch.state_id == state_id
            and patch.global_current_rev >= anchor_revision
            and patch.global_future_rev <= target_revision
            and (session_id is None or patch.session_id == session_id)
        ]
        patches = sorted(patches, key=lambda item: item.global_current_rev)

        last_global_revision = anchor.global_revision
        last_timepoint = anchor.event_time

        for patch in patches:
            patch_document = self._to_patch_document(patch.op, patch.path, patch.value)
            current_state = cast(
                JSONSerializable,
                jsonpatch.apply_patch(current_state, [patch_document], in_place=False),
            )
            last_global_revision = patch.global_future_rev
            last_timepoint = patch.event_time

        return Snapshot(
            timepoint=last_timepoint,
            data=copy.deepcopy(current_state),
            global_revision=last_global_revision,
            session_id=anchor.session_id or "",
        )

    def _to_patch_event(self, patch: WritePatchReq) -> PatchEvent:
        return PatchEvent(
            timepoint=patch.event_time,
            state_id=patch.state_id,
            global_current_rev=patch.global_current_rev,
            global_future_rev=patch.global_future_rev,
            correlation_id=patch.correlation_id or "",
            session_id=patch.session_id or "",
            patch=self._to_patch_document(patch.op, patch.path, patch.value),
        )

    def _to_snapshot(self, snapshot: WriteSnapshotReq) -> Snapshot:
        return Snapshot(
            timepoint=snapshot.event_time,
            data=copy.deepcopy(snapshot.state_data),
            global_revision=snapshot.global_revision,
            session_id=snapshot.session_id or "",
        )

    def _to_patch_document(
        self, op: str, path: str, value: JSONSerializable | None
    ) -> dict[str, JSONSerializable]:
        patch_document: dict[str, JSONSerializable] = {"op": op, "path": path}
        if op != "remove":
            patch_document["value"] = value
        return patch_document

    def _get_patches(self) -> list[WritePatchReq]:
        if self.store is None:
            return []
        return list(self.store.patches)

    def _get_snapshots(self) -> list[WriteSnapshotReq]:
        if self.store is None:
            return []
        return list(self.store.snapshots)

    def _get_state_ids(self, session_id: Optional[str]) -> list[str]:
        state_ids = {
            snapshot.state_id
            for snapshot in self._get_snapshots()
            if session_id is None or snapshot.session_id == session_id
        }
        state_ids.update(
            patch.state_id
            for patch in self._get_patches()
            if session_id is None or patch.session_id == session_id
        )
        return sorted(state_ids)
