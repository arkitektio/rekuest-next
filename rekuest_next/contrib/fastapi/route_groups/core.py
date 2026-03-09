"""Core agent command and websocket route builders."""

from __future__ import annotations

import uuid
from typing import Any, Callable

from fastapi import APIRouter, Request

from rekuest_next.messages import Assign, Cancel, Pause, Resume, Step
from rekuest_next.api.schema import AssignInput, CancelInput, PauseInput, ResumeInput, StepInput
from rekuest_next.contrib.fastapi.agent import FastApiAgent


def build_core_router(
    agent: FastApiAgent,
    get_user_from_request: Callable[[Request], Any],
    assign_path: str = "/assign",
    cancel_path: str = "/cancel",
    pause_path: str = "/pause",
    resume_path: str = "/resume",
    step_path: str = "/step",
) -> APIRouter:
    """Build the core command routes for task lifecycle control.

    The dedicated websocket routes live in the task, state, and lock route
    groups. This router only exposes command-style HTTP endpoints.
    """
    router = APIRouter(tags=["Agent"])

    async def assign_base_action(request: Request, extension: str = "default") -> dict[str, str]:
        """Submit a task using the interface provided in the request body."""
        user = get_user_from_request(request)
        payload = await request.json()
        interface = payload.pop("interface", None)
        assign_input = AssignInput(
            **{
                **payload,
                "cached": payload.get("cached", False),
                "log": payload.get("log", False),
                "capture": payload.get("capture", False),
                "ephemeral": payload.get("ephemeral", False),
                "instanceId": payload.get("instanceID", "fastapi_instance"),
            }
        )
        assignation_id = str(uuid.uuid4())
        assign_message = Assign(
            interface=interface,
            extension=extension,
            assignation=assignation_id,
            args=assign_input.args,
            user=str(user),
            step=assign_input.step,
            app="fastapi",
            action="api_call",
        )
        await agent.transport.asubmit(assign_message)
        return {"status": "submitted", "assignation": assignation_id}

    async def assign_action(
        request: Request, interface: str, extension: str = "default"
    ) -> dict[str, str]:
        """Submit a task for a concrete interface path parameter."""
        user = get_user_from_request(request)
        payload = await request.json()
        assign_input = AssignInput(**{**payload, "interface": interface})
        assignation_id = str(uuid.uuid4())
        assign_message = Assign(
            interface=interface,
            extension=extension,
            assignation=assignation_id,
            args=assign_input.args,
            step=assign_input.step,
            user=str(user),
            app="fastapi",
            action="api_call",
        )
        await agent.transport.asubmit(assign_message)
        return {"status": "submitted", "assignation": assignation_id}

    async def cancel_action(request: Request) -> dict[str, str]:
        """Request cancellation of a running task."""
        payload = await request.json()
        cancel_input = CancelInput(**payload)
        await agent.transport.asubmit(Cancel(assignation=cancel_input.assignation))
        return {"status": "cancelling", "assignation": cancel_input.assignation}

    async def pause_action(request: Request) -> dict[str, str]:
        """Request pausing of a running task."""
        payload = await request.json()
        pause_input = PauseInput(**payload)
        await agent.transport.asubmit(Pause(assignation=pause_input.assignation))
        return {"status": "pausing", "assignation": pause_input.assignation}

    async def resume_action(request: Request) -> dict[str, str]:
        """Request resuming of a paused task."""
        payload = await request.json()
        resume_input = ResumeInput(**payload)
        await agent.transport.asubmit(Resume(assignation=resume_input.assignation))
        return {"status": "resuming", "assignation": resume_input.assignation}

    async def step_action(request: Request) -> dict[str, str]:
        """Request a single step for a stepping-capable task."""
        payload = await request.json()
        step_input = StepInput(**payload)
        await agent.transport.asubmit(Step(assignation=step_input.assignation))
        return {"status": "stepping", "assignation": step_input.assignation}

    router.add_api_route(assign_path, assign_base_action, methods=["POST"])
    router.add_api_route(f"{assign_path}/{{interface}}", assign_action, methods=["POST"])
    router.add_api_route(cancel_path, cancel_action, methods=["POST"])
    router.add_api_route(pause_path, pause_action, methods=["POST"])
    router.add_api_route(resume_path, resume_action, methods=["POST"])
    router.add_api_route(step_path, step_action, methods=["POST"])
    return router
