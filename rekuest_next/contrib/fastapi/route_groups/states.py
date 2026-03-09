"""State overview route builders."""

from __future__ import annotations

from fastapi import APIRouter, Query

from rekuest_next.contrib.fastapi.agent import FastApiAgent
from rekuest_next.contrib.fastapi.models import StateCollectionResponse

from .common import normalize_filter_values


def build_state_router(
    agent: FastApiAgent,
    states_path: str = "/states",
) -> APIRouter:
    """Build overview routes for published states."""
    router = APIRouter(tags=["States"])

    async def list_states(
        state_keys: list[str] | None = Query(default=None),
    ) -> StateCollectionResponse:
        normalized_state_keys = normalize_filter_values(state_keys)
        return await agent.aget_state_views(normalized_state_keys)

    router.add_api_route(
        states_path,
        list_states,
        methods=["GET"],
        response_model=StateCollectionResponse,
        summary="List states",
        description="List current states filtered by optional state keys.",
    )
    return router
