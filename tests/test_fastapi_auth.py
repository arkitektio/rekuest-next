"""Tests for the unified `expand_user_from_request` authentication hook.

The hook is the one place an application defines who may talk to an agent. It has to
work over both transports, because a browser can set an `Authorization` header on a
`fetch` but not on a `WebSocket` constructor - so the websocket authenticates in band,
from the init payload it already sends after connecting.
"""

from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from rekuest_next.app import AppRegistry
from rekuest_next.contrib.fastapi.agent import FastApiAgent
from rekuest_next.contrib.fastapi.auth import (
    AuthenticationError,
    UserSource,
    default_expand_user_from_request,
    resolve_expand_user_from_request,
    wrap_legacy_get_user_from_request,
)
from rekuest_next.contrib.fastapi.models import WebSocketSubscriptionInit
from rekuest_next.contrib.fastapi.routes import add_agent_routes

GOOD_TOKEN = "let-me-in"


def build_app(**kwargs: Any) -> FastAPI:
    """Build a bare app exposing only the core agent routes."""
    app = FastAPI()
    agent = FastApiAgent(app_registry=AppRegistry())
    app.state.agent = agent
    add_agent_routes(app, agent, **kwargs)
    return app


def expand_user(source: UserSource) -> str:
    """Accept `GOOD_TOKEN` from either transport, reject everything else."""
    if isinstance(source, WebSocketSubscriptionInit):
        token = source.token
    else:
        token = source.headers.get("authorization")
    if token != GOOD_TOKEN:
        raise AuthenticationError("bad token")
    return "trusted-user"


# --------------------------------------------------------------------------- model


def test_init_payload_carries_a_token() -> None:
    """The websocket's stand-in for an `Authorization` header."""
    init = WebSocketSubscriptionInit.model_validate({"type": "INIT", "token": "abc"})
    assert init.token == "abc"


def test_init_payload_token_is_optional() -> None:
    """Existing clients send no token and must keep validating."""
    assert WebSocketSubscriptionInit.model_validate({"type": "INIT"}).token is None


# ------------------------------------------------------------------------ resolver


def test_resolver_prefers_the_unified_hook() -> None:
    def legacy(_: Request) -> str:
        return "legacy"

    resolved = resolve_expand_user_from_request(expand_user, legacy)
    assert resolved is expand_user


def test_resolver_falls_back_to_the_permissive_default() -> None:
    """An app that configures no hook stays unauthenticated, as it was before."""
    resolved = resolve_expand_user_from_request(None, None)
    assert resolved is default_expand_user_from_request
    assert resolved(WebSocketSubscriptionInit()) == "anonymous"


def test_legacy_hook_never_sees_an_init_payload() -> None:
    """The legacy signature only ever accepted a Request, so it must not be handed one.

    Passing a `WebSocketSubscriptionInit` to a callable written for a `Request` would
    fail at the first attribute access, turning a working app into a broken one on
    upgrade.
    """
    seen: list[Any] = []

    def legacy(request: Request) -> str:
        seen.append(request)
        return "legacy"

    wrapped = wrap_legacy_get_user_from_request(legacy)
    assert wrapped(WebSocketSubscriptionInit(token="whatever")) == "anonymous"
    assert seen == []


# ---------------------------------------------------------------------------- http


def test_http_rejection_answers_401() -> None:
    client = TestClient(build_app(expand_user_from_request=expand_user))
    response = client.post("/assign", json={"interface": "noop"})
    assert response.status_code == 401


def test_http_401_carries_no_www_authenticate_header() -> None:
    """That header makes browsers open their own credential dialog.

    An application driving its own login page must not have the browser's native
    Basic prompt appear on top of it.
    """
    client = TestClient(build_app(expand_user_from_request=expand_user))
    response = client.post("/assign", json={"interface": "noop"})
    assert "www-authenticate" not in {key.lower() for key in response.headers}


# ----------------------------------------------------------------------- websocket


def test_websocket_rejects_a_missing_token_with_1008() -> None:
    """1008 rather than a pre-accept refusal.

    Rejecting before `accept()` fails the HTTP handshake, which browsers surface as an
    opaque 1006 - indistinguishable from a dropped connection, so a client cannot tell
    "log in again" from "the network blipped". Accepting first buys a real close code.
    """
    client = TestClient(build_app(expand_user_from_request=expand_user))
    with pytest.raises(WebSocketDisconnect) as excinfo:  # noqa: PT012
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({"type": "INIT"})
            websocket.receive_json()
    assert excinfo.value.code == 1008


def test_websocket_rejects_a_wrong_token_with_1008() -> None:
    client = TestClient(build_app(expand_user_from_request=expand_user))
    with pytest.raises(WebSocketDisconnect) as excinfo:  # noqa: PT012
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({"type": "INIT", "token": "nope"})
            websocket.receive_json()
    assert excinfo.value.code == 1008


def test_websocket_accepts_a_good_token() -> None:
    client = TestClient(build_app(expand_user_from_request=expand_user))
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json({"type": "INIT", "token": GOOD_TOKEN})
        assert websocket.receive_json()["type"] == "INIT"


def test_websocket_without_a_hook_stays_open() -> None:
    """Back-compat: an app that never configured auth is unaffected."""
    client = TestClient(build_app())
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json({"type": "INIT"})
        assert websocket.receive_json()["type"] == "INIT"


def test_legacy_http_hook_leaves_the_websocket_open() -> None:
    """Upgrading must not silently start rejecting websockets.

    An app that only ever passed the HTTP-only hook expressed nothing about websocket
    access, so the socket keeps its previous behaviour rather than closing.
    """
    client = TestClient(build_app(get_user_from_request=lambda _: "legacy"))
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json({"type": "INIT"})
        assert websocket.receive_json()["type"] == "INIT"
