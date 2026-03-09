"""Schema inspection route builders."""

from __future__ import annotations

from fastapi import APIRouter

from rekuest_next.contrib.fastapi.agent import FastApiAgent


def build_schema_router(
    agent: FastApiAgent,
    extension: str = "default",
) -> APIRouter:
    """Build schema inspection routes."""
    router = APIRouter(tags=["Schemas"])

    async def get_implementation_schemas() -> dict:
        implementations = {}
        for impl in agent.extension_registry.get(extension).get_static_implementations():
            implementations[impl.interface or impl.definition.name] = impl
        return {"count": len(implementations), "implementations": implementations}

    async def get_state_schemas() -> dict:
        state_schemas = {}
        for agent_extension in agent.extension_registry.agent_extensions.values():
            for interface, schema in agent_extension.get_state_schemas().items():
                state_schemas[interface] = schema
        return {"count": len(state_schemas), "states": state_schemas}

    async def get_lock_schemas() -> dict:
        lock_schemas = {}
        for agent_extension in agent.extension_registry.agent_extensions.values():
            for interface, schema in agent_extension.get_lock_schemas().items():
                lock_schemas[interface] = schema
        return {"count": len(lock_schemas), "locks": lock_schemas}

    router.add_api_route("/schemas/implementations", get_implementation_schemas, methods=["GET"])
    router.add_api_route("/schemas/states", get_state_schemas, methods=["GET"])
    router.add_api_route("/schemas/locks", get_lock_schemas, methods=["GET"])
    return router
