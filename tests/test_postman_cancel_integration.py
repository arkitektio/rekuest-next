"""Integration smoke test for postman cancel-confirmation against the real backend.

Stands up a fresh ``RekuestNext`` (via :func:`build_fresh_rekuest`) on the shared
deployment, registers a long-running action, starts a call, then cancels it. Because
the GraphQL postman now awaits the backend's CANCELLED confirmation before re-raising,
by the time the ``CancelledError`` surfaces the server-side task must already be in the
CANCELLED state — which we assert by reading it back over GraphQL.
"""

import asyncio
import uuid

import pytest
from dokker import Deployment

from rekuest_next.api.schema import TaskEventKind, amy_implementation_at, arequests
from rekuest_next.remote import acall

from .conftest import CONNECT_TIMEOUT, build_fresh_rekuest


async def _find_task(reference: str):
    """Return the task with ``reference`` from the backend, or ``None``."""
    for task in await arequests():
        if task.reference == reference:
            return task
    return None


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_cancel_awaits_backend_cancelled(deployment: Deployment) -> None:
    """Cancelling a call reaches the backend and the task ends up CANCELLED."""

    app = build_fresh_rekuest(deployment, token="standalone_token")

    async def sleeper(seconds: int) -> int:
        """Sleep for a while, then return — long enough to be cancelled mid-flight."""
        await asyncio.sleep(seconds)
        return seconds

    app.register(sleeper)

    async with app as app:
        await app.aconnect(timeout=CONNECT_TIMEOUT)
        loop_task = asyncio.create_task(app.aloop())

        impl = await amy_implementation_at("sleeper")

        reference = f"cancel-smoke-{uuid.uuid4().hex[:8]}"
        call_task = asyncio.create_task(acall(impl, seconds=30, reference=reference))

        # Wait until the backend has registered and started the task.
        async def _started() -> bool:
            task = await _find_task(reference)
            return task is not None and task.latest_event_kind not in (
                TaskEventKind.QUEUED,
                TaskEventKind.BOUND,
            )

        deadline = asyncio.get_event_loop().time() + 10.0
        while not await _started():
            assert asyncio.get_event_loop().time() < deadline, "task never started"
            await asyncio.sleep(0.2)

        # Cancel: the postman sends the cancel and awaits the CANCELLED confirmation
        # before this CancelledError propagates.
        call_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await call_task

        task = await _find_task(reference)
        assert task is not None, "task disappeared from the backend"
        assert task.latest_event_kind == TaskEventKind.CANCELLED, (
            f"expected CANCELLED, got {task.latest_event_kind}"
        )

        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass
