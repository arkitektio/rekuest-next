"""OpenAPI and schema helpers for FastAPI route builders."""

from typing import Any

from fastapi import FastAPI
from fastapi import APIRouter
from fastapi.openapi.utils import get_openapi

from rekuest_next.api.schema import ArgPortInput, PortKind


CUSTOM_SCHEMAS_STATE_KEY = "rekuest_custom_schemas"


def port_to_json_schema(port: ArgPortInput) -> dict[str, Any]:
    """Convert a port definition to JSON schema."""
    schema: dict[str, Any] = {}

    if port.label:
        schema["title"] = port.label
    if port.description:
        schema["description"] = port.description
    if port.kind == PortKind.INT:
        schema["type"] = "integer"
    elif port.kind == PortKind.STRING:
        schema["type"] = "string"
    elif port.kind == PortKind.BOOL:
        schema["type"] = "boolean"
    elif port.kind == PortKind.FLOAT:
        schema["type"] = "number"
    elif port.kind == PortKind.LIST:
        schema["type"] = "array"
        schema["items"] = port_to_json_schema(port.children[0]) if port.children else {}
    elif port.kind in (PortKind.DICT, PortKind.STRUCTURE):
        schema["type"] = "object"
        if port.children:
            schema["properties"] = {
                child.key: port_to_json_schema(child) for child in port.children
            }
            required = [
                child.key
                for child in port.children
                if not child.nullable and child.default is None
            ]
            if required:
                schema["required"] = required
        else:
            schema["additionalProperties"] = True
    else:
        schema["type"] = ["string", "number", "boolean", "object", "array", "null"]

    if port.identifier:
        schema["x-identifier"] = port.identifier
    if port.choices:
        schema["enum"] = [choice.value for choice in port.choices]
    if port.default is not None:
        schema["default"] = port.default
    if port.nullable and isinstance(schema.get("type"), str):
        schema["type"] = [schema["type"], "null"]

    return schema


def create_json_schema_from_ports(
    ports: tuple[ArgPortInput, ...],
    schema_title: str,
) -> dict[str, Any]:
    """Create a JSON schema document for a tuple of ports."""
    if not ports:
        return {"type": "object", "title": schema_title, "properties": {}}

    properties: dict[str, Any] = {}
    required: list[str] = []
    for port in ports:
        properties[port.key] = port_to_json_schema(port)
        if not port.nullable and port.default is None:
            required.append(port.key)

    schema: dict[str, Any] = {
        "type": "object",
        "title": schema_title,
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


def register_custom_schema(app: FastAPI, name: str, schema: dict[str, Any]) -> None:
    """Register a reusable OpenAPI schema on the app state."""
    schemas = getattr(app.state, CUSTOM_SCHEMAS_STATE_KEY, None)
    if schemas is None:
        schemas = {}
        setattr(app.state, CUSTOM_SCHEMAS_STATE_KEY, schemas)
    schemas[name] = schema


def register_router_custom_schemas(app: FastAPI, router: APIRouter) -> None:
    """Transfer custom schemas attached to a router onto the app state."""
    router_schemas = getattr(router, "_custom_schemas", {})
    for name, schema in router_schemas.items():
        register_custom_schema(app, name, schema)


def configure_openapi(app: FastAPI) -> None:
    """Configure custom OpenAPI generation with registered schemas."""

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        openapi_schema.setdefault("components", {}).setdefault("schemas", {})
        custom_schemas = getattr(app.state, CUSTOM_SCHEMAS_STATE_KEY, {})
        openapi_schema["components"]["schemas"].update(custom_schemas)
        app.openapi_schema = openapi_schema
        return openapi_schema

    app.openapi = custom_openapi
