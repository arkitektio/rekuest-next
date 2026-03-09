"""Lock-related FastAPI route helpers."""

from typing import Any

from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from rekuest_next.api.schema import LockSchemaInput
from rekuest_next.contrib.fastapi.agent import FastApiAgent

from .common import normalize_filter_values


def build_lock_snapshot(
    agent: FastApiAgent,
    lock_keys: list[str] | None = None,
) -> dict[str, object]:
    """Build the current lock snapshot for websocket initialization."""
    normalized_lock_keys = normalize_filter_values(lock_keys)
    locks: dict[str, dict[str, object | None]] = {}

    for interface, lock in agent.locks.items():
        key = lock.lock_schema.key
        if (
            normalized_lock_keys is not None
            and interface not in normalized_lock_keys
            and key not in normalized_lock_keys
        ):
            continue

        locking_task = lock.locking_task
        locks[interface] = {
            "interface": interface,
            "key": key,
            "task_id": str(locking_task) if locking_task else None,
        }

    return {
        "count": len(locks),
        "locks": locks,
    }


def add_lock_websocket_route(
    app: FastAPI,
    agent: FastApiAgent,
    ws_path: str = "/ws/locks",
) -> None:
    """Register the lock websocket route."""

    @app.websocket(ws_path)
    async def lock_updates_stream_websocket(websocket: WebSocket) -> None:
        lock_keys = normalize_filter_values(list(websocket.query_params.getlist("lock_keys")))
        initial_message: dict[str, Any] = {
            "type": "LOCK_INIT",
            **build_lock_snapshot(agent, lock_keys),
        }
        await agent.transport.handle_lock_websocket(
            websocket,
            lock_keys=set(lock_keys) if lock_keys is not None else None,
            initial_message=initial_message,
        )


def add_lock_route(
    app: FastAPI,
    agent: FastApiAgent,
    interface: str,
    lock_schema: LockSchemaInput,
    locks_path: str = "/locks",
) -> None:
    """Add a GET route for a specific lock to the FastAPI app."""
    route_path = f"{locks_path}/{interface}"
    response_schema_name = f"{lock_schema.key}Lock"
    response_schema = {
        "type": "object",
        "title": response_schema_name,
        "properties": {
            "key": {"type": "string", "description": "The lock key"},
            "task_id": {"type": "string", "description": "The task holding the lock"},
        },
    }

    if not hasattr(app, "_custom_schemas"):
        app._custom_schemas = {}
    app._custom_schemas[response_schema_name] = response_schema

    async def get_lock_endpoint() -> JSONResponse:
        if interface not in agent.locks:
            return JSONResponse(
                status_code=404,
                content={"error": "Lock not initialized", "interface": interface},
            )

        locking_task = agent.locks[interface].locking_task
        return JSONResponse(
            content={
                "key": lock_schema.key,
                "task_id": str(locking_task) if locking_task else None,
            }
        )

    route = APIRoute(
        path=route_path,
        endpoint=get_lock_endpoint,
        methods=["GET"],
        summary=f"Get {lock_schema.key} lock",
        description=f"Get the current value of the {lock_schema.key} lock",
        tags=["Locks"],
        response_class=JSONResponse,
        openapi_extra={
            "responses": {
                "200": {
                    "description": "Current lock value",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/locks/{response_schema_name}"}
                        }
                    },
                }
            },
        },
    )
    app.router.routes.append(route)


def add_lock_routes(
    app: FastAPI,
    agent: FastApiAgent,
    locks_path: str = "/locks",
    locks_ws_path: str = "/ws/locks",
) -> None:
    """Add routes for all registered locks in the agent."""

    @app.get(locks_path)
    async def list_locks() -> dict:
        locks_info = {}
        for interface, lock in agent.locks.items():
            locking_task = lock.locking_task
            locks_info[interface] = {
                "key": lock.lock_schema.key,
                "task_id": str(locking_task) if locking_task else None,
            }
        return {"count": len(locks_info), "locks": locks_info}

    all_lock_schemas = {}
    for extension in agent.extension_registry.agent_extensions.values():
        all_lock_schemas.update(extension.get_lock_schemas())

    for interface, lock_schema in all_lock_schemas.items():
        add_lock_route(app, agent, interface, lock_schema, locks_path)

    @app.websocket(locks_ws_path)
    async def lock_updates_websocket(websocket: WebSocket) -> None:
        lock_keys = normalize_filter_values(list(websocket.query_params.getlist("lock_keys")))
        initial_message: dict[str, Any] = {
            "type": "LOCK_INIT",
            **build_lock_snapshot(agent, lock_keys),
        }
        await agent.transport.handle_lock_websocket(
            websocket,
            lock_keys=set(lock_keys) if lock_keys is not None else None,
            initial_message=initial_message,
        )
