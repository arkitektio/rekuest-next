"""State detail and retriever route builders."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from rekuest_next.api.schema import StateImplementationInput
from rekuest_next.contrib.fastapi.retriever.protocol import (
    PatchEvent as RetrieverPatchEvent,
)
from rekuest_next.contrib.fastapi.retriever.protocol import (
    SessionBoundary as RetrieverSessionBoundary,
)
from rekuest_next.contrib.fastapi.retriever.protocol import (
    Snapshot as RetrieverSnapshot,
)
from rekuest_next.contrib.fastapi.retriever.protocol import (
    TaskBoundary as RetrieverTaskBoundary,
)

from rekuest_next.contrib.fastapi.agent import FastApiAgent
from rekuest_next.contrib.fastapi.models import (
    RetrieverPatchEventResponse,
    RetrieverSessionBoundaryResponse,
    RetrieverSessionInfoResponse,
    RetrieverSnapshotResponse,
    RetrieverTaskBoundaryResponse,
    StateCollectionResponse,
    StateSegmentsResponse,
)
from rekuest_next.contrib.fastapi.openapi_utils import create_json_schema_from_ports
from rekuest_next.contrib.fastapi.route_groups.common import normalize_filter_values


def _to_task_boundary_response(
    boundary: RetrieverTaskBoundary,
) -> RetrieverTaskBoundaryResponse:
    return RetrieverTaskBoundaryResponse(
        correlation_id=boundary.correlation_id,
        start_global_revision=boundary.start_global_revision,
        end_global_revision=boundary.end_global_revision,
        start_time=boundary.start_time,
        end_time=boundary.end_time,
    )


def _to_session_boundary_response(
    boundary: RetrieverSessionBoundary,
) -> RetrieverSessionBoundaryResponse:
    return RetrieverSessionBoundaryResponse(
        session_id=boundary.session_id,
        start_global_revision=boundary.start_global_revision,
        end_global_revision=boundary.end_global_revision,
        start_time=boundary.start_time,
        end_time=boundary.end_time,
    )


def _to_snapshot_response(snapshot: RetrieverSnapshot) -> RetrieverSnapshotResponse:
    return RetrieverSnapshotResponse(
        timepoint=snapshot.timepoint,
        data=snapshot.data,
        global_revision=snapshot.global_revision,
        session_id=snapshot.session_id,
    )


def _to_patch_event_response(event: RetrieverPatchEvent) -> RetrieverPatchEventResponse:
    return RetrieverPatchEventResponse(
        timepoint=event.timepoint,
        state_id=event.state_id,
        global_current_rev=event.global_current_rev,
        global_future_rev=event.global_future_rev,
        correlation_id=event.correlation_id,
        session_id=event.session_id,
        patch=event.patch,
    )


def _serialize_snapshot_result(
    result: RetrieverSnapshot | list[RetrieverSnapshot] | None,
) -> RetrieverSnapshotResponse | list[RetrieverSnapshotResponse]:
    if result is None:
        raise HTTPException(
            status_code=404, detail="No state found for the requested revision"
        )
    if isinstance(result, list):
        return [_to_snapshot_response(snapshot) for snapshot in result]
    return _to_snapshot_response(result)


def _resolve_session_id(agent: FastApiAgent, session_id: str | None) -> str:
    """Return the explicit session id or the agent's current one, else 404."""
    resolved_session_id = session_id or agent.current_session
    if not resolved_session_id:
        raise HTTPException(status_code=404, detail="No active session")
    return resolved_session_id


def _resolve_state_query(
    state_keys: list[str] | None,
    states: dict[str, StateImplementationInput],
    session_id: str | None,
    agent: FastApiAgent,
) -> tuple[list[str] | None, str]:
    """Normalize a state-key filter and resolve the session for history queries.

    Unknown state keys are rejected with 422 rather than silently widening
    the query to every state.
    """
    normalized_state_keys = normalize_filter_values(state_keys)
    if normalized_state_keys is not None:
        missing_state_keys = [
            state_key for state_key in normalized_state_keys if state_key not in states
        ]
        if missing_state_keys:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown state keys: {', '.join(missing_state_keys)}",
            )
    return normalized_state_keys, _resolve_session_id(agent, session_id)


async def _aget_session_boundary_response(
    agent: FastApiAgent, session_id: str, state_id: str | None
) -> RetrieverSessionBoundaryResponse:
    boundary = await agent.retriever.aget_session_boundaries(
        session_id, state_id=state_id
    )
    if boundary is None:
        raise HTTPException(status_code=404, detail="Session boundaries not found")
    return _to_session_boundary_response(boundary)


def _build_boundary_routes(agent: FastApiAgent, states_path: str) -> APIRouter:
    """Session info and task/session revision-boundary endpoints."""
    router = APIRouter()

    async def session_info() -> RetrieverSessionInfoResponse:
        return RetrieverSessionInfoResponse(current_session=agent.current_session)

    async def task_boundaries(
        correlation_id: str,
        state_id: str | None = Query(default=None),
    ) -> RetrieverTaskBoundaryResponse:
        """Return task boundaries expressed in global revisions."""
        boundary = await agent.retriever.aget_task_boundaries(
            correlation_id, state_id=state_id
        )
        if boundary is None:
            raise HTTPException(status_code=404, detail="Task boundaries not found")
        return _to_task_boundary_response(boundary)

    async def active_session_boundaries(
        state_id: str | None = Query(default=None),
    ) -> RetrieverSessionBoundaryResponse:
        """Return active-session boundaries expressed in global revisions."""
        return await _aget_session_boundary_response(
            agent, _resolve_session_id(agent, None), state_id
        )

    async def state_session_boundaries(
        session_id: str | None = Query(default=None),
        state_id: str | None = Query(default=None),
    ) -> RetrieverSessionBoundaryResponse:
        """Return session boundaries expressed in global revisions."""
        return await _aget_session_boundary_response(
            agent, _resolve_session_id(agent, session_id), state_id
        )

    async def session_boundaries(
        session_id: str,
        state_id: str | None = Query(default=None),
    ) -> RetrieverSessionBoundaryResponse:
        """Return session boundaries expressed in global revisions."""
        return await _aget_session_boundary_response(agent, session_id, state_id)

    router.add_api_route(
        "/session_info",
        session_info,
        methods=["GET"],
        response_model=RetrieverSessionInfoResponse,
    )
    router.add_api_route(
        "/task_boundaries/{correlation_id}",
        task_boundaries,
        methods=["GET"],
        response_model=RetrieverTaskBoundaryResponse,
        summary="Get task global revision boundaries",
        description="Return the start and end global revisions covered by the task.",
    )
    router.add_api_route(
        "/active_session_boundaries",
        active_session_boundaries,
        methods=["GET"],
        response_model=RetrieverSessionBoundaryResponse,
        summary="Get active session global revision boundaries",
        description="Return the start and end global revisions covered by the active session.",
    )
    router.add_api_route(
        f"{states_path}/session_boundaries",
        state_session_boundaries,
        methods=["GET"],
        response_model=RetrieverSessionBoundaryResponse,
        summary="Get session global revision boundaries",
        description="Return the start and end global revisions covered by the resolved session.",
    )
    router.add_api_route(
        "/session_boundaries/{session_id}",
        session_boundaries,
        methods=["GET"],
        response_model=RetrieverSessionBoundaryResponse,
        summary="Get session global revision boundaries by id",
        description="Return the start and end global revisions covered by the requested session.",
    )
    return router


def _build_checkout_routes(
    agent: FastApiAgent,
    states: dict[str, StateImplementationInput],
    states_path: str,
) -> APIRouter:
    """Checkout and segment endpoints over a set of state keys."""
    router = APIRouter()

    async def state_checkout(
        global_revision_id: int = Query(ge=0),
        state_keys: list[str] | None = Query(default=None),
        session_id: str | None = Query(default=None),
        recent_patch_count: int = Query(default=5, ge=0),
    ) -> StateCollectionResponse:
        normalized_state_keys, resolved_session_id = _resolve_state_query(
            state_keys, states, session_id, agent
        )

        state_response = await agent.aget_checkout_state_views(
            global_revision_id=global_revision_id,
            state_keys=normalized_state_keys,
            session_id=resolved_session_id,
        )
        if recent_patch_count == 0:
            state_response.recent_patches = []
            return state_response

        recent_events = await agent.retriever.aget_patch_events_between_global_revs(
            from_global_revision=0,
            to_global_revision=global_revision_id,
            state_ids=normalized_state_keys,
            session_id=resolved_session_id,
        )
        state_response.recent_patches = [
            _to_patch_event_response(event)
            for event in recent_events[-recent_patch_count:]
        ]
        return state_response

    async def state_segments(
        from_global_revision_id: int = Query(ge=0),
        to_global_revision_id: int = Query(ge=0),
        state_keys: list[str] | None = Query(default=None),
        session_id: str | None = Query(default=None),
    ) -> StateSegmentsResponse:
        normalized_state_keys, resolved_session_id = _resolve_state_query(
            state_keys, states, session_id, agent
        )

        events = await agent.retriever.aget_patch_events_between_global_revs(
            from_global_revision=from_global_revision_id,
            to_global_revision=to_global_revision_id,
            state_ids=normalized_state_keys,
            session_id=resolved_session_id,
        )
        return StateSegmentsResponse(
            from_global_revision=from_global_revision_id,
            to_global_revision=to_global_revision_id,
            patches=[_to_patch_event_response(event) for event in events],
        )

    router.add_api_route(
        f"{states_path}/checkout",
        state_checkout,
        methods=["GET"],
        response_model=StateCollectionResponse,
    )
    router.add_api_route(
        f"{states_path}/segments",
        state_segments,
        methods=["GET"],
        response_model=StateSegmentsResponse,
    )
    return router


def _build_history_routes(agent: FastApiAgent) -> APIRouter:
    """Snapshot and patch-event history endpoints."""
    router = APIRouter()

    async def state_at_global(
        session_id: str,
        target_revision: int,
        state_id: str | None = Query(default=None),
    ) -> RetrieverSnapshotResponse | list[RetrieverSnapshotResponse]:
        return _serialize_snapshot_result(
            await agent.retriever.aget_state_at_global_rev(
                target_revision, state_id=state_id, session_id=session_id
            )
        )

    async def current_state_at_global(
        target_revision: int,
        state_id: str | None = Query(default=None),
    ) -> RetrieverSnapshotResponse | list[RetrieverSnapshotResponse]:
        session_id = _resolve_session_id(agent, None)
        return _serialize_snapshot_result(
            await agent.retriever.aget_state_at_global_rev(
                target_revision, state_id=state_id, session_id=session_id
            )
        )

    async def forward_events(
        session_id: str,
        after_global_revision: int,
        state_id: str | None = Query(default=None),
        count: int = Query(default=100, ge=1),
    ) -> list[RetrieverPatchEventResponse]:
        """Return patch events whose global revision starts at or after `after_global_revision`."""
        events = await agent.retriever.aget_forward_events_after_rev(
            after_global_revision,
            state_id=state_id,
            session_id=session_id,
            count=count,
        )
        return [_to_patch_event_response(event) for event in events]

    async def snapshots_around(
        session_id: str,
        target_revision: int,
        state_id: str | None = Query(default=None),
        before: int = Query(default=1, ge=0),
        after: int = Query(default=1, ge=0),
    ) -> list[RetrieverSnapshotResponse]:
        snapshots = await agent.retriever.aget_snapshots_around_rev(
            target_revision,
            state_id=state_id,
            session_id=session_id,
            before=before,
            after=after,
        )
        return [_to_snapshot_response(snapshot) for snapshot in snapshots]

    router.add_api_route(
        "/state_at_global/{session_id}/{target_revision}",
        state_at_global,
        methods=["GET"],
        response_model=RetrieverSnapshotResponse | list[RetrieverSnapshotResponse],
    )
    router.add_api_route(
        "/current_state_at_global/{target_revision}",
        current_state_at_global,
        methods=["GET"],
        response_model=RetrieverSnapshotResponse | list[RetrieverSnapshotResponse],
    )
    router.add_api_route(
        "/forward_events/{session_id}/{after_global_revision}",
        forward_events,
        methods=["GET"],
        response_model=list[RetrieverPatchEventResponse],
        summary="Get forward events after a global revision",
        description="Return patch events whose global revision range starts at or after `after_global_revision`.",
    )
    router.add_api_route(
        "/snapshots_around/{session_id}/{target_revision}",
        snapshots_around,
        methods=["GET"],
        response_model=list[RetrieverSnapshotResponse],
    )
    return router


def _add_per_state_routes(
    router: APIRouter,
    agent: FastApiAgent,
    states: dict[str, StateImplementationInput],
    states_path: str,
) -> None:
    """Register one current-value endpoint per state on the given router.

    These must live on the top-level router because their custom JSON
    schemas are attached to it and collected by
    ``register_router_custom_schemas``.
    """

    def _build_current_state_endpoint(interface: str):
        async def current_state() -> JSONResponse:
            if interface not in agent.states:
                return JSONResponse(
                    status_code=404,
                    content={"error": "State not initialized", "interface": interface},
                )
            revised_state = await agent.aget_revised_state(interface)
            return JSONResponse(
                content={
                    "revision": revised_state.revision,
                    "state": revised_state.data,
                }
            )

        return current_state

    for interface, state_schema in states.items():
        response_schema_name = f"{state_schema.definition.name}State"
        router.__dict__.setdefault("_custom_schemas", {})[response_schema_name] = (
            create_json_schema_from_ports(
                state_schema.definition.ports, response_schema_name
            )
        )
        router.add_api_route(
            f"{states_path}/{interface}",
            _build_current_state_endpoint(interface),
            methods=["GET"],
            summary=f"Get {state_schema.definition.name} state",
            description=f"Get the current value of the {state_schema.definition.name} state",
            tags=["States", "State Details"],
            response_class=JSONResponse,
        )


def build_state_detail_router(
    agent: FastApiAgent,
    states: dict[str, StateImplementationInput],
    states_path: str = "/states",
) -> APIRouter:
    """Build detail routes for current and historical state access."""
    router = APIRouter(tags=["States", "State Details"])
    _add_per_state_routes(router, agent, states, states_path)
    router.include_router(_build_boundary_routes(agent, states_path))
    router.include_router(_build_checkout_routes(agent, states, states_path))
    router.include_router(_build_history_routes(agent))
    return router
