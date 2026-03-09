"""Lock overview and websocket route builders."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, WebSocket

from rekuest_next.contrib.fastapi.agent import FastApiAgent
from rekuest_next.contrib.fastapi.models import LockCollectionResponse

from .common import normalize_filter_values


def build_lock_router(
    agent: FastApiAgent[Any],
    locks_path: str = "/locks",
    locks_ws_path: str = "/ws/locks",
) -> APIRouter:
    """Build overview routes for managed locks."""
    router = APIRouter(tags=["Locks"])

    async def list_locks(
        lock_keys: list[str] | None = Query(default=None),
    ) -> LockCollectionResponse:
        normalized_lock_keys = normalize_filter_values(lock_keys)
        locks = await agent.aget_lock_views(normalized_lock_keys)
        return LockCollectionResponse(count=len(locks), locks=locks)

    async def lock_updates(websocket: WebSocket) -> None:
        lock_keys = normalize_filter_values(
            list(websocket.query_params.getlist("lock_keys"))
        )
        locks = await agent.aget_lock_views(lock_keys)
        initial_message: dict[str, Any] = {
            "type": "LOCK_INIT",
            "count": len(locks),
            "locks": {
                key: value.model_dump(mode="json") for key, value in locks.items()
            },
        }
        await agent.transport.handle_lock_websocket(
            websocket,
            lock_keys=set(lock_keys) if lock_keys is not None else None,
            initial_message=initial_message,
        )

    router.add_api_route(
        locks_path,
        list_locks,
        methods=["GET"],
        response_model=LockCollectionResponse,
        summary="List locks",
        description="List current locks filtered by optional lock keys.",
    )
    router.add_api_websocket_route(locks_ws_path, lock_updates)
    return router
