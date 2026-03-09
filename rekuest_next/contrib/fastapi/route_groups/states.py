"""State-related FastAPI route helpers."""

import asyncio
import copy
from typing import Any

from fastapi import FastAPI, HTTPException, Query, WebSocket
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel

from rekuest_next.api.schema import StateSchemaInput
from rekuest_next.contrib.fastapi.agent import FastApiAgent

from .common import normalize_filter_values


class GlobalStateItemResponse(BaseModel):
    """Response item for a single global state."""

    interface: str
    name: str
    initialized: bool
    revision: int
    value: Any | None = None


class GlobalStatesResponse(BaseModel):
    """Response payload for global state queries."""

    current_session: str | None
    count: int
    states: dict[str, GlobalStateItemResponse]


def collect_state_schemas(agent: FastApiAgent) -> dict[str, StateSchemaInput]:
    """Collect all registered state schemas from every extension."""
    state_schemas: dict[str, StateSchemaInput] = {}
    for extension in agent.extension_registry.agent_extensions.values():
        state_schemas.update(extension.get_state_schemas())
    return state_schemas


def select_state_schemas(
    agent: FastApiAgent,
    state_keys: list[str] | None,
) -> dict[str, StateSchemaInput]:
    """Select a subset of state schemas, validating provided keys."""
    state_schemas = collect_state_schemas(agent)
    normalized_state_keys = normalize_filter_values(state_keys)
    if normalized_state_keys is None:
        return state_schemas

    missing = [key for key in normalized_state_keys if key not in state_schemas]
    if missing:
        raise HTTPException(status_code=404, detail={"missing_state_keys": missing})

    return {key: state_schemas[key] for key in normalized_state_keys}


def build_global_states_response(
    agent: FastApiAgent,
    state_keys: list[str] | None = None,
) -> GlobalStatesResponse:
    """Build the current global state payload with per-state revisions."""
    selected_state_schemas = select_state_schemas(agent, state_keys)
    states: dict[str, GlobalStateItemResponse] = {}

    for interface, schema in selected_state_schemas.items():
        states[interface] = GlobalStateItemResponse(
            interface=interface,
            name=schema.name,
            initialized=interface in agent.states,
            revision=agent._state_revisions.get(interface, 0),
            value=copy.deepcopy(agent._current_shrunk_states.get(interface)),
        )

    return GlobalStatesResponse(
        current_session=agent.current_session,
        count=len(states),
        states=states,
    )


def global_state_revision_token(response: GlobalStatesResponse) -> dict[str, int]:
    """Build a comparable revision token for a global state snapshot."""
    return {interface: state.revision for interface, state in response.states.items()}


def add_state_websocket_route(
    app: FastAPI,
    agent: FastApiAgent,
    ws_path: str = "/ws/states",
) -> None:
    """Register the scoped state websocket route."""

    @app.websocket(ws_path)
    async def state_stream_websocket(websocket: WebSocket) -> None:
        state_keys = normalize_filter_values(list(websocket.query_params.getlist("state_keys")))
        try:
            initial_payload = build_global_states_response(agent, state_keys)
        except HTTPException as exc:
            await websocket.accept()
            await websocket.send_json({"type": "STATE_ERROR", "detail": exc.detail})
            await websocket.close(code=1008)
            return

        await agent.transport.handle_state_websocket(
            websocket,
            state_keys=set(state_keys) if state_keys is not None else None,
            initial_message={"type": "STATE_INIT", **initial_payload.model_dump(mode="json")},
        )


def add_state_route(
    app: FastAPI,
    agent: FastApiAgent,
    interface: str,
    state_schema: StateSchemaInput,
    states_path: str = "/states",
) -> None:
    """Add a GET route for a specific state to the FastAPI app."""
    route_path = f"{states_path}/{interface}"
    response_schema_name = f"{state_schema.name}State"
    response_schema = {
        "type": "object",
        "title": response_schema_name,
        "properties": {},
    }

    from rekuest_next.contrib.fastapi.routes import create_json_schema_from_ports

    response_schema = create_json_schema_from_ports(state_schema.ports, response_schema_name)

    if not hasattr(app, "_custom_schemas"):
        app._custom_schemas = {}
    app._custom_schemas[response_schema_name] = response_schema

    async def get_state_endpoint() -> JSONResponse:
        if interface not in agent.states:
            return JSONResponse(
                status_code=404,
                content={"error": "State not initialized", "interface": interface},
            )

        try:
            revised_state = await agent.aget_revised_state(interface)
            return JSONResponse(
                content={
                    "revision": revised_state.revision,
                    "state": revised_state.data,
                }
            )
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={"error": f"Failed to serialize state: {str(exc)}"},
            )

    route = APIRoute(
        path=route_path,
        endpoint=get_state_endpoint,
        methods=["GET"],
        summary=f"Get {state_schema.name} state",
        description=f"Get the current value of the {state_schema.name} state",
        tags=["States"],
        response_class=JSONResponse,
        openapi_extra={
            "responses": {
                "200": {
                    "description": "Current state value",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{response_schema_name}"}
                        }
                    },
                }
            },
        },
    )
    app.router.routes.append(route)


def add_state_routes(
    app: FastAPI,
    agent: FastApiAgent,
    states_path: str = "/states",
    states_ws_path: str = "/states/ws",
) -> None:
    """Add routes for all registered states in the agent."""
    all_state_schemas = collect_state_schemas(agent)

    @app.get(states_path, response_model=GlobalStatesResponse)
    @app.get(f"{states_path}/global", response_model=GlobalStatesResponse)
    async def list_states(
        state_keys: list[str] | None = Query(default=None),
    ) -> GlobalStatesResponse:
        return build_global_states_response(agent, state_keys)

    for interface, state_schema in all_state_schemas.items():
        add_state_route(app, agent, interface, state_schema, states_path)

    @app.websocket(f"{states_ws_path}/global")
    async def global_state_updates_websocket(websocket: WebSocket) -> None:
        state_keys = normalize_filter_values(list(websocket.query_params.getlist("state_keys")))
        try:
            initial_payload = build_global_states_response(agent, state_keys)
        except HTTPException as exc:
            await websocket.accept()
            await websocket.send_json({"type": "GLOBAL_STATE_ERROR", "detail": exc.detail})
            await websocket.close(code=1008)
            return

        await websocket.accept()
        await websocket.send_json(
            {"type": "GLOBAL_STATE_INIT", **initial_payload.model_dump(mode="json")}
        )
        last_revisions = global_state_revision_token(initial_payload)

        try:
            while True:
                try:
                    await asyncio.wait_for(websocket.receive(), timeout=0.2)
                except asyncio.TimeoutError:
                    pass

                current_payload = build_global_states_response(agent, state_keys)
                current_revisions = global_state_revision_token(current_payload)
                if current_revisions != last_revisions:
                    await websocket.send_json(
                        {"type": "GLOBAL_STATE_UPDATE", **current_payload.model_dump(mode="json")}
                    )
                    last_revisions = current_revisions
        except Exception:
            return

    @app.websocket(states_ws_path)
    async def state_updates_websocket(websocket: WebSocket) -> None:
        initial_payload = build_global_states_response(agent)
        await agent.transport.handle_state_websocket(
            websocket,
            initial_message={"type": "STATE_INIT", **initial_payload.model_dump(mode="json")},
        )
