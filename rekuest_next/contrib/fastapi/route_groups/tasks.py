"""Task overview route builders."""

from __future__ import annotations

from typing import TypeVar

from fastapi import APIRouter, Query

from rekuest_next.contrib.fastapi.agent import FastApiAgent
from rekuest_next.contrib.fastapi.models import TaskCollectionResponse

from .common import normalize_filter_values

T = TypeVar("T")


def build_task_router(
    agent: FastApiAgent[T],
    tasks_path: str = "/tasks",
) -> APIRouter:
    """Build overview routes for managed tasks."""
    router = APIRouter(tags=["Tasks"])

    async def list_tasks(
        action_keys: list[str] | None = Query(default=None),
    ) -> TaskCollectionResponse:
        normalized_action_keys = normalize_filter_values(action_keys)
        return await agent.aget_task_views(normalized_action_keys)

    router.add_api_route(
        tasks_path,
        list_tasks,
        methods=["GET"],
        response_model=TaskCollectionResponse,
        summary="List tasks",
        description="List current tasks filtered by optional action keys.",
    )
    return router
