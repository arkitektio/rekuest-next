"""Schema inspection route builders."""

from __future__ import annotations

from fastapi import APIRouter

from rekuest_next.contrib.fastapi.agent import FastApiAgent


def build_schema_router(
    agent: FastApiAgent,
) -> APIRouter:
    """Build schema inspection routes."""
    router = APIRouter(tags=["Schemas"])

    async def get_implementation_schemas() -> dict:
        implementations = {}
        for impl in agent.app_registry.get_implementations():
            implementations[impl.interface or impl.definition.name] = impl
        return {"count": len(implementations), "implementations": implementations}

    async def get_state_schemas() -> dict:
        state_schemas = dict(agent.app_registry.states)
        return {"count": len(state_schemas), "states": state_schemas}

    async def get_lock_schemas() -> dict:
        lock_schemas = {
            lock.key: lock for lock in agent.app_registry.get_locks()
        }
        return {"count": len(lock_schemas), "locks": lock_schemas}

    async def get_blok_schemas() -> dict:
        blok_schemas = agent.app_registry.get_declared_bloks()
        return {"count": len(blok_schemas), "bloks": blok_schemas}

    router.add_api_route(
        "/schemas/implementations", get_implementation_schemas, methods=["GET"]
    )
    router.add_api_route("/schemas/states", get_state_schemas, methods=["GET"])
    router.add_api_route("/schemas/locks", get_lock_schemas, methods=["GET"])
    router.add_api_route("/schemas/bloks", get_blok_schemas, methods=["GET"])
    return router
