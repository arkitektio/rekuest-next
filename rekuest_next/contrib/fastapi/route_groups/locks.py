"""Lock overview route builders."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from rekuest_next.contrib.fastapi.agent import FastApiAgent
from rekuest_next.contrib.fastapi.models import LockCollectionResponse

from .common import normalize_filter_values


def build_lock_router(
    agent: FastApiAgent[Any],
    locks_path: str = "/locks",
) -> APIRouter:
    """Build overview routes for managed locks."""
    router = APIRouter(tags=["Locks"])

    async def list_locks(
        lock_keys: list[str] | None = Query(default=None),
    ) -> LockCollectionResponse:
        normalized_lock_keys = normalize_filter_values(lock_keys)
        locks = await agent.aget_lock_views(normalized_lock_keys)
        return LockCollectionResponse(count=len(locks), locks=locks)

    router.add_api_route(
        locks_path,
        list_locks,
        methods=["GET"],
        response_model=LockCollectionResponse,
        summary="List locks",
        description="List current locks filtered by optional lock keys.",
    )
    return router
