"""Implementation route builders."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from rekuest_next.api.schema import ImplementationInput
from rekuest_next.contrib.fastapi.agent import FastApiAgent
from rekuest_next.contrib.fastapi.openapi_utils import (
    create_json_schema_from_ports,
)


def add_implementation_route(
    router: APIRouter,
    agent: FastApiAgent,
    implementation: ImplementationInput,
) -> None:
    """Register a single implementation execution route."""
    route_path = f"/{implementation.interface or implementation.definition.name}"
    request_schema_name = f"{implementation.definition.name}Request"
    response_schema_name = f"{implementation.definition.name}Response"
    args_schema_name = f"{implementation.definition.name}Args"
    args_schema = create_json_schema_from_ports(
        implementation.definition.args, args_schema_name
    )
    request_schema = {
        "type": "object",
        "title": request_schema_name,
        "properties": {
            "args": args_schema,
            "policy": {
                "type": "object",
                "description": "The policy for the assignation",
            },
            "reference": {"type": "string", "description": "A reference string"},
            "cached": {"type": "boolean", "default": False},
            "log": {"type": "boolean", "default": False},
            "capture": {"type": "boolean", "default": False},
            "ephemeral": {"type": "boolean", "default": False},
            "step": {
                "type": "boolean",
                "description": "Whether to step through the assignation",
            },
        },
        "required": ["args", "cached", "log", "capture", "ephemeral"],
    }
    response_schema = create_json_schema_from_ports(
        implementation.definition.returns,
        response_schema_name,
    )

    async def implementation_endpoint(request: Request) -> JSONResponse:
        payload = await request.json()
        assign_input = agent.build_assign_input(
            payload,
            interface=implementation.interface or implementation.definition.name,
        )
        assign = agent.build_assign_message(
            assign_input,
            user="fastapi",
        )
        result = await agent.transport.asubmit(assign)
        return JSONResponse(content={"status": "submitted", "task_id": result})

    router.add_api_route(
        route_path,
        implementation_endpoint,
        methods=["POST"],
        summary=implementation.definition.name,
        description=implementation.definition.description
        or f"Execute {implementation.definition.name} action",
        tags=list(implementation.definition.collections)
        if implementation.definition.collections
        else [],
        response_class=JSONResponse,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": f"#/components/schemas/{request_schema_name}"
                        }
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "Successful Response",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": f"#/components/schemas/{response_schema_name}"
                            }
                        }
                    },
                }
            },
        },
    )
    # schema registration happens on the app once router is included
    router.__dict__.setdefault("_custom_schemas", {})[request_schema_name] = (
        request_schema
    )
    router.__dict__.setdefault("_custom_schemas", {})[response_schema_name] = (
        response_schema
    )


def build_implementation_router(
    agent: FastApiAgent,
) -> APIRouter:
    """Build routes for all static implementations."""
    router = APIRouter()
    for implementation in agent.app_registry.get_implementations():
        add_implementation_route(router, agent, implementation)
    return router
