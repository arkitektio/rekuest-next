"""State overview and websocket route builders."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, WebSocket

from rekuest_next.contrib.fastapi.agent import FastApiAgent
from rekuest_next.contrib.fastapi.models import StateCollectionResponse

from .common import normalize_filter_values


def build_state_router(
    agent: FastApiAgent,
    states_path: str = "/states",
    states_ws_path: str = "/ws/states",
) -> APIRouter:
    """Build overview routes for published states."""
    router = APIRouter(tags=["States"])

    async def list_states(
        state_keys: list[str] | None = Query(default=None),
    ) -> StateCollectionResponse:
        normalized_state_keys = normalize_filter_values(state_keys)
        return await agent.aget_state_views(normalized_state_keys)

    async def state_updates(websocket: WebSocket) -> None:
        state_keys = normalize_filter_values(
            list(websocket.query_params.getlist("state_keys"))
        )
        initial_payload = await agent.aget_state_views(state_keys)
        initial_message: dict[str, Any] = {
            "type": "STATE_INIT",
            **initial_payload.model_dump(mode="json"),
        }
        await agent.transport.handle_state_websocket(
            websocket,
            state_keys=set(state_keys) if state_keys is not None else None,
            initial_message=initial_message,
        )

    router.add_api_route(
        states_path,
        list_states,
        methods=["GET"],
        response_model=StateCollectionResponse,
        summary="List states",
        description="List current states filtered by optional state keys.",
    )
    router.add_api_websocket_route(states_ws_path, state_updates)
    return router
