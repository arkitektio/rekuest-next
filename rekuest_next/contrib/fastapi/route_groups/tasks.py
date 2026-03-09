"""Task-related FastAPI route helpers."""

from typing import Any

from fastapi import FastAPI, WebSocket

from rekuest_next.contrib.fastapi.agent import FastApiAgent

from .common import normalize_filter_values


def build_task_snapshot(
    agent: FastApiAgent,
    assignation_ids: list[str] | None = None,
) -> dict[str, object]:
    """Build the current task snapshot for websocket initialization."""
    normalized_assignation_ids = normalize_filter_values(assignation_ids)
    tasks: dict[str, dict[str, object | None]] = {}

    for assignation_id, assign_message in agent.managed_assignments.items():
        if (
            normalized_assignation_ids is not None
            and assignation_id not in normalized_assignation_ids
        ):
            continue

        tasks[assignation_id] = {
            "assignation": assignation_id,
            "interface": assign_message.interface,
            "extension": assign_message.extension,
            "user": assign_message.user,
            "app": assign_message.app,
            "action": assign_message.action,
            "running": assignation_id in agent.running_assignments,
            "actor_id": agent.running_assignments.get(assignation_id),
        }

    return {
        "count": len(tasks),
        "tasks": tasks,
    }


def add_task_websocket_route(
    app: FastAPI,
    agent: FastApiAgent,
    ws_path: str = "/ws/tasks",
) -> None:
    """Register the task websocket route."""

    @app.websocket(ws_path)
    async def task_updates_websocket(websocket: WebSocket) -> None:
        assignation_ids = normalize_filter_values(
            list(websocket.query_params.getlist("assignation_ids"))
        )
        initial_message: dict[str, Any] = {
            "type": "TASK_INIT",
            **build_task_snapshot(agent, assignation_ids),
        }
        await agent.transport.handle_task_websocket(
            websocket,
            assignation_ids=set(assignation_ids) if assignation_ids is not None else None,
            initial_message=initial_message,
        )
