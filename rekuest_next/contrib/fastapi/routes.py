"""FastAPI route orchestration for rekuest_next agents."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any, Optional, TypeVar

from fastapi import APIRouter, FastAPI, Request

from rekuest_next.app import AppRegistry
from rekuest_next.contrib.fastapi.agent import FastApiAgent
from rekuest_next.contrib.fastapi.detail_routes import (
    build_state_detail_router,
    build_task_detail_router,
)
from rekuest_next.contrib.fastapi.openapi_utils import (
    configure_openapi,
    create_json_schema_from_ports,
    port_to_json_schema,
    register_router_custom_schemas,
)
from rekuest_next.contrib.fastapi.route_groups import (
    add_implementation_route,
    build_core_router,
    build_implementation_router,
    build_lock_router,
    build_schema_router,
    build_state_router,
    build_task_router,
)
from rekuest_next.contrib.sql_lite.retriever import SQLLiteRetriever
from rekuest_next.contrib.sql_lite.sink import SQLLiteSink

logger = logging.getLogger(__name__)


def _default_user_from_request(_: Request) -> str:
    return "anonymous"


def _include_router(app: FastAPI, router: APIRouter) -> None:
    app.include_router(router)
    register_router_custom_schemas(app, router)


T = TypeVar("T")


def create_lifespan(
    agent: FastApiAgent[T],
    app_context: T | None = None,
) -> Callable[[FastAPI], contextlib.AbstractAsyncContextManager[None]]:
    """Create a FastAPI lifespan manager for a configured agent."""

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.agent = agent
        async with agent:
            provide_task = asyncio.create_task(agent.aprovide(context=app_context))
            yield
            provide_task.cancel()
            try:
                await provide_task
            except asyncio.CancelledError:
                logger.info("Provide task cancelled during shutdown")
            except Exception as exc:
                logger.error(
                    "Error during provide task shutdown: %s", exc, exc_info=True
                )

    return lifespan


def add_agent_routes(
    app: FastAPI,
    agent: FastApiAgent[Any],
    get_user_from_request: Optional[Callable[[Request], object]] = None,
    assign_path: str = "/assign",
    cancel_path: str = "/cancel",
    pause_path: str = "/pause",
    resume_path: str = "/resume",
    step_path: str = "/step",
) -> None:
    """Include core agent routes."""
    user_getter = get_user_from_request or _default_user_from_request
    _include_router(
        app,
        build_core_router(
            agent,
            user_getter,
            assign_path=assign_path,
            cancel_path=cancel_path,
            pause_path=pause_path,
            resume_path=resume_path,
            step_path=step_path,
        ),
    )


def add_task_routes(
    app: FastAPI,
    agent: FastApiAgent[T],
    tasks_path: str = "/tasks",
    tasks_ws_path: str = "/wstasks",
) -> None:
    """Include task overview routes."""
    _include_router(
        app,
        build_task_router(agent, tasks_path=tasks_path, tasks_ws_path=tasks_ws_path),
    )


def add_task_detail_routes(
    app: FastAPI,
    agent: FastApiAgent,
    tasks_path: str = "/tasks",
) -> None:
    """Include conditional task detail routes."""
    _include_router(app, build_task_detail_router(agent, tasks_path=tasks_path))


def add_state_routes(
    app: FastAPI,
    agent: FastApiAgent,
    states_path: str = "/states",
    states_ws_path: str = "/wsstates",
) -> None:
    """Include state overview routes."""
    _include_router(
        app,
        build_state_router(
            agent, states_path=states_path, states_ws_path=states_ws_path
        ),
    )


def add_state_detail_routes(
    app: FastAPI,
    agent: FastApiAgent,
    states_path: str = "/states",
    state_schemas: dict[str, object] | None = None,
) -> None:
    """Include conditional state detail and retriever routes."""
    state_schemas = state_schemas or agent.get_state_schemas()
    _include_router(
        app, build_state_detail_router(agent, state_schemas, states_path=states_path)
    )


def add_lock_routes(
    app: FastAPI,
    agent: FastApiAgent,
    locks_path: str = "/locks",
    locks_ws_path: str = "/wslocks",
) -> None:
    """Include lock overview routes."""
    _include_router(
        app,
        build_lock_router(agent, locks_path=locks_path, locks_ws_path=locks_ws_path),
    )


def add_implementation_routes(
    app: FastAPI,
    agent: FastApiAgent,
    extension: str = "default",
) -> None:
    """Include all implementation execution routes."""
    _include_router(app, build_implementation_router(agent, extension=extension))


def add_schema_routes(
    app: FastAPI,
    agent: FastApiAgent,
    extension: str = "default",
) -> None:
    """Include schema inspection routes."""
    _include_router(app, build_schema_router(agent, extension=extension))


T = TypeVar("T")


def configure_fastapi(
    app: FastAPI,
    app_registry: AppRegistry,
    get_user_from_request: Optional[Callable[[Request], object]] = None,
    add_implementations: bool = True,
    add_schema: bool = True,
    add_states: bool = True,
    add_state_details: bool = True,
    add_locks: bool = True,
    add_tasks: bool = True,
    add_task_details: bool = True,
    extension: str = "default",
    tasks_path: str = "/tasks",
    tasks_ws_path: str = "/ws/tasks",
    assign_path: str = "/assign",
    states_path: str = "/states",
    states_ws_path: str = "/ws/states",
    locks_path: str = "/locks",
    locks_ws_path: str = "/ws/locks",
    app_context: T | None = None,
) -> FastApiAgent[T]:
    """Configure a FastAPI app with a refactored set of agent route groups."""
    from rekuest_next.agents.extensions.default import DefaultExtension
    from rekuest_next.agents.registry import ExtensionRegistry

    default_extension = DefaultExtension(app_registry=app_registry)
    extension_registry = ExtensionRegistry()
    extension_registry.register(default_extension)

    db_file = "db_like.db"
    agent: FastApiAgent[T] = FastApiAgent(  # type: ignore
        extension_registry=extension_registry,
        retriever=SQLLiteRetriever(db_path=db_file),
        sink=SQLLiteSink(db_path=db_file),
    )

    add_agent_routes(
        app,
        agent,
        get_user_from_request=get_user_from_request,
        assign_path=assign_path,
    )

    @contextlib.asynccontextmanager
    async def lifespan(fastapi_app: FastAPI) -> AsyncIterator[None]:
        if add_tasks:
            add_task_routes(
                fastapi_app, agent, tasks_path=tasks_path, tasks_ws_path=tasks_ws_path
            )
        if add_task_details:
            add_task_detail_routes(fastapi_app, agent, tasks_path=tasks_path)
        if add_states:
            add_state_routes(
                fastapi_app,
                agent,
                states_path=states_path,
                states_ws_path=states_ws_path,
            )
        if add_state_details:
            add_state_detail_routes(
                fastapi_app,
                agent,
                states_path=states_path,
                state_schemas=await agent.aget_state_schemas(),
            )
        if add_locks:
            add_lock_routes(
                fastapi_app, agent, locks_path=locks_path, locks_ws_path=locks_ws_path
            )
        if add_implementations:
            add_implementation_routes(fastapi_app, agent, extension=extension)
        if add_schema:
            add_schema_routes(fastapi_app, agent, extension=extension)

        configure_openapi(fastapi_app)
        fastapi_app.state.agent = agent

        async with agent:
            provide_task = asyncio.create_task(agent.aprovide(context=app_context))
            yield
            provide_task.cancel()
            try:
                await provide_task
            except asyncio.CancelledError:
                logger.info("Provide task cancelled during shutdown")
            except Exception as exc:
                logger.error(
                    "Error during provide task shutdown: %s", exc, exc_info=True
                )

    app.router.lifespan_context = lifespan
    return agent


__all__ = [
    "add_agent_routes",
    "add_implementation_route",
    "add_implementation_routes",
    "add_lock_routes",
    "add_schema_routes",
    "add_state_detail_routes",
    "add_state_routes",
    "add_task_detail_routes",
    "add_task_routes",
    "configure_fastapi",
    "configure_openapi",
    "create_json_schema_from_ports",
    "create_lifespan",
    "port_to_json_schema",
]
