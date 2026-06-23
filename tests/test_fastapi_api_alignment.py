from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from rekuest_next.api.schema import (
    ImplementationInput,
    PortKind,
    ReturnPortInput,
    StateDefinitionInput,
    StateImplementationInput,
)
from rekuest_next.contrib.fastapi.agent import FastApiAgent
from rekuest_next.contrib.fastapi.route_groups.implementations import (
    add_implementation_route,
)
from rekuest_next.contrib.fastapi.route_groups.schemas import build_schema_router
from rekuest_next.contrib.fastapi.routes import add_state_detail_routes
from rekuest_next.app import AppRegistry
from rekuest_next.definition.define import prepare_definition


def test_fastapi_agent_build_assign_input_defaults_flags() -> None:
    agent = FastApiAgent()

    assign_input = agent.build_assign_input(
        {
            "args": {"value": "hello"},
            "capture": True,
        },
        interface="echo",
    )

    assert assign_input.interface == "echo"
    assert assign_input.capture is True
    assert assign_input.cached is False
    assert assign_input.log is False
    assert assign_input.ephemeral is False


def test_fastapi_agent_build_assign_message_uses_normalized_assign_input() -> None:
    agent = FastApiAgent()
    assign_input = agent.build_assign_input(
        {
            "args": {"value": "hello"},
            "reference": "ref-1",
            "capture": True,
            "cached": True,
            "log": True,
            "ephemeral": False,
        },
        interface="echo",
    )

    assign_message = agent.build_assign_message(assign_input, user="alice")

    assert assign_message.interface == "echo"
    assert assign_message.user == "alice"
    assert assign_message.org == "fastapi"
    assert assign_message.implementation == "fastapi"
    assert assign_message.action == "api_call"
    assert assign_message.reference == "ref-1"
    assert assign_message.capture is True
    assert assign_message.args == {"value": "hello"}


def test_add_state_detail_routes_uses_current_agent_state_accessor() -> None:
    app = FastAPI()
    agent = FastApiAgent()

    add_state_detail_routes(app, agent)

    paths = {route.path for route in app.routes}
    assert "/session_info" in paths
    assert "/states/checkout" in paths


def test_schema_router_uses_app_registry_states() -> None:
    app = FastAPI()
    agent = FastApiAgent()
    app_registry = AppRegistry()
    app_registry.states["demo_state"] = StateImplementationInput(
        interface="demo_state",
        definition=StateDefinitionInput(
            name="DemoState",
            ports=(
                ReturnPortInput(
                    key="value",
                    kind=PortKind.STRING,
                    nullable=False,
                ),
            ),
        ),
    )
    agent.app_registry = app_registry

    app.include_router(build_schema_router(agent))

    with TestClient(app) as client:
        response = client.get("/schemas/states")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert "demo_state" in body["states"]


def test_schema_router_exposes_blok_implementation_inputs() -> None:
    app = FastAPI()
    agent = FastApiAgent()
    app_registry = AppRegistry()
    app_registry.register_blok("demo_blok", "<Page />", description="Demo blok")
    agent.app_registry = app_registry

    app.include_router(build_schema_router(agent))

    with TestClient(app) as client:
        response = client.get("/schemas/bloks")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert "demo_blok" in body["bloks"]


def test_implementation_route_reuses_fastapi_assign_builder(simple_registry) -> None:
    app = FastAPI()
    agent = FastApiAgent()

    captured = []

    async def capture_submit(message):
        captured.append(message)
        return message.task

    object.__setattr__(agent.transport, "asubmit", capture_submit)

    def echo(value: str) -> str:
        return value

    implementation = ImplementationInput(
        definition=prepare_definition(echo, structure_registry=simple_registry),
        dependencies=(),
        dynamic=False,
        interface="echo",
        needs_token=True,
    )

    router = APIRouter()
    add_implementation_route(router, agent, implementation)
    app.include_router(router)

    with TestClient(app) as client:
        response = client.post(
            "/echo",
            json={"args": {"value": "hello"}},
        )

    assert response.status_code == 200
    assert len(captured) == 1
    assert captured[0].interface == "echo"
    assert captured[0].user == "fastapi"
    assert captured[0].org == "fastapi"
    assert captured[0].implementation == "fastapi"
    assert captured[0].action == "api_call"
