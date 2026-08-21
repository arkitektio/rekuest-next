"""Core agent command and websocket route builders."""

from __future__ import annotations
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request, WebSocket

from rekuest_next.contrib.fastapi.auth import (
    AuthenticationError,
    ExpandUserFromRequest,
)
from rekuest_next.messages import Cancel, Pause, Resume
from rekuest_next.api.schema import (
    CancelInput,
    PauseInput,
    ResumeInput,
)
from rekuest_next.contrib.fastapi.agent import FastApiAgent


def build_core_router(
    agent: FastApiAgent,
    get_user_from_request: Callable[[Request], Any],
    expand_user_from_request: ExpandUserFromRequest | None = None,
    ws_path: str = "/ws",
    assign_path: str = "/assign",
    cancel_path: str = "/cancel",
    pause_path: str = "/pause",
    resume_path: str = "/resume",
    step_path: str = "/step",
) -> APIRouter:
    """Build the core command routes for task lifecycle control.

    The websocket endpoint expects an init JSON payload after connect with
    optional `action_keys`, `state_keys`, and `lock_keys` arrays.

    When `expand_user_from_request` is given it authenticates both transports: the
    HTTP routes hand it the `Request`, the websocket hands it the init payload. It
    supersedes the HTTP-only `get_user_from_request`, which stays supported so
    existing callers keep working.
    """
    router = APIRouter(tags=["Agent"])

    def resolve_http_user(request: Request) -> Any:
        """Expand the user for an HTTP route, answering 401 on rejection."""
        if expand_user_from_request is None:
            return get_user_from_request(request)
        try:
            return expand_user_from_request(request)
        except AuthenticationError as auth_error:
            # No `WWW-Authenticate` header: it makes browsers pop their native
            # credential dialog, which fights an application's own login page.
            raise HTTPException(status_code=401, detail="Not authorized") from auth_error

    async def websocket_endpoint(websocket: WebSocket) -> None:
        """Serve the unified websocket endpoint for tasks, states, and locks."""
        await agent.handle_websocket(
            websocket,
            expand_user_from_request=expand_user_from_request,
        )

    async def assign_base_action(request: Request) -> dict[str, str]:
        """Submit a task using the interface provided in the request body."""
        user = resolve_http_user(request)
        payload = await request.json()
        interface = payload.pop("interface", None)
        assign_input = agent.build_assign_input(
            payload,
            interface=interface,
        )
        assign_message = agent.build_assign_message(
            assign_input,
            user=str(user),
        )
        await agent.transport.asubmit(assign_message)
        return {"status": "submitted", "task": assign_message.task}

    async def assign_action(request: Request, interface: str) -> dict[str, str]:
        """Submit a task for a concrete interface path parameter."""
        user = resolve_http_user(request)
        payload = await request.json()
        assign_input = agent.build_assign_input(payload, interface=interface)
        assign_message = agent.build_assign_message(
            assign_input,
            user=str(user),
        )
        await agent.transport.asubmit(assign_message)
        return {"status": "submitted", "task": assign_message.task}

    async def cancel_action(request: Request) -> dict[str, str]:
        """Request cancellation of a running task."""
        payload = await request.json()
        cancel_input = CancelInput(**payload)
        await agent.transport.asubmit(Cancel(task=cancel_input.task))
        return {"status": "cancelling", "task": cancel_input.task}

    async def pause_action(request: Request) -> dict[str, str]:
        """Request pausing of a running task."""
        payload = await request.json()
        pause_input = PauseInput(**payload)
        await agent.transport.asubmit(Pause(task=pause_input.task))
        return {"status": "pausing", "task": pause_input.task}

    async def resume_action(request: Request) -> dict[str, str]:
        """Request resuming of a paused task."""
        payload = await request.json()
        resume_input = ResumeInput(**payload)
        await agent.transport.asubmit(Resume(task=resume_input.task))
        return {"status": "resuming", "task": resume_input.task}

    async def step_action(request: Request) -> dict[str, str]:
        """Request a single step for a stepping-capable task."""
        payload = await request.json()
        task = payload["task"]
        await agent.transport.asubmit(Resume(task=task, step=True))
        return {"status": "stepping", "task": task}

    router.add_api_websocket_route(ws_path, websocket_endpoint)
    router.add_api_route(assign_path, assign_base_action, methods=["POST"])
    router.add_api_route(
        f"{assign_path}/{{interface}}", assign_action, methods=["POST"]
    )
    router.add_api_route(cancel_path, cancel_action, methods=["POST"])
    router.add_api_route(pause_path, pause_action, methods=["POST"])
    router.add_api_route(resume_path, resume_action, methods=["POST"])
    router.add_api_route(step_path, step_action, methods=["POST"])
    return router
