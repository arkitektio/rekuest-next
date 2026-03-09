"""Task detail route builders."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from rekuest_next.contrib.fastapi.agent import FastApiAgent
from rekuest_next.contrib.fastapi.models import TaskView


def build_task_detail_router(
    agent: FastApiAgent,
    tasks_path: str = "/tasks",
) -> APIRouter:
    """Build detail routes for managed tasks."""
    router = APIRouter(tags=["Tasks", "Task Details"])

    async def get_task(task_id: str) -> TaskView | JSONResponse:
        task_views = await agent.aget_task_views()
        task = task_views.tasks.get(task_id)
        if task is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Task not found", "task_id": task_id},
            )
        return task

    router.add_api_route(
        f"{tasks_path}/{{task_id}}",
        get_task,
        methods=["GET"],
        response_model=TaskView,
        summary="Get task details",
    )
    return router
