"""Implementation route builders."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from rekuest_next.api.schema import AssignInput, ImplementationInput
from rekuest_next.contrib.fastapi.agent import FastApiAgent
from rekuest_next.messages import Assign
from rekuest_next.contrib.fastapi.openapi_utils import (
    create_json_schema_from_ports,
    register_custom_schema,
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
    args_schema = create_json_schema_from_ports(implementation.definition.args, args_schema_name)
    request_schema = {
        "type": "object",
        "title": request_schema_name,
        "properties": {
            "args": args_schema,
            "policy": {"type": "object", "description": "The policy for the assignation"},
            "instanceId": {"type": "string", "description": "The instance ID"},
            "reference": {"type": "string", "description": "A reference string"},
            "cached": {"type": "boolean", "default": False},
            "log": {"type": "boolean", "default": False},
            "capture": {"type": "boolean", "default": False},
            "ephemeral": {"type": "boolean", "default": False},
            "step": {"type": "boolean", "description": "Whether to step through the assignation"},
        },
        "required": ["args", "instanceId", "cached", "log", "capture", "ephemeral"],
    }
    response_schema = create_json_schema_from_ports(
        implementation.definition.returns,
        response_schema_name,
    )

    async def implementation_endpoint(request: Request) -> JSONResponse:
        payload = await request.json()
        assign_input = AssignInput(
            **{
                **payload,
                "interface": implementation.interface,
                "instanceId": payload.get("instanceId", "fastapi_instance"),
            }
        )
        assign = Assign(
            interface=assign_input.interface or implementation.definition.name,
            extension="default",
            assignation=str(uuid.uuid4()),
            args=assign_input.args,
            reference=assign_input.reference,
            user="fastapi",
            step=assign_input.step,
            app="fastapi",
            action="api_call",
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
                        "schema": {"$ref": f"#/components/schemas/{request_schema_name}"}
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "Successful Response",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{response_schema_name}"}
                        }
                    },
                }
            },
        },
    )
    # schema registration happens on the app once router is included
    router.__dict__.setdefault("_custom_schemas", {})[request_schema_name] = request_schema
    router.__dict__.setdefault("_custom_schemas", {})[response_schema_name] = response_schema


def build_implementation_router(
    agent: FastApiAgent,
    extension: str = "default",
) -> APIRouter:
    """Build routes for all static implementations."""
    router = APIRouter()
    for implementation in agent.extension_registry.get(extension).get_static_implementations():
        add_implementation_route(router, agent, implementation)
    return router
