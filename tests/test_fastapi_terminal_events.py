"""Terminal task events must reach FastAPI websocket subscribers.

The agent prunes a finished task from ``managed_assignments`` when it reports a
terminal event, and the FastAPI transport routes task events to websocket
subscribers by looking the assignment up. Pruning *before* the send made every
COMPLETED/ERROR unroutable: clients saw PROGRESS and YIELD but never the end.
"""

from pathlib import Path
from collections.abc import Generator

import pytest
from fastapi import FastAPI

from rekuest_next.app import AppRegistry
from rekuest_next.contrib.fastapi.routes import configure_fastapi
from rekuest_next.contrib.fastapi.testing import AsyncAgentTestClient


def _build_app(tmp_path: Path) -> FastAPI:
    registry = AppRegistry()

    def count_up(until: int) -> Generator[int, None, None]:
        """Yield the numbers below ``until``."""
        yield from range(until)

    def explode() -> int:
        """Always fail."""
        raise ValueError("boom")

    registry.register(count_up)
    registry.register(explode)

    app = FastAPI()
    configure_fastapi(app, registry, db_file=str(tmp_path / "agent.db"))
    return app


@pytest.mark.asyncio
async def test_a_completed_task_delivers_completed_over_the_websocket(tmp_path: Path) -> None:
    async with AsyncAgentTestClient(_build_app(tmp_path), as_user="tester") as client:
        result = await client.assign("count_up", {"until": 2})
        events = await client.collect_until_done(result.task_id, timeout=5)

    kinds = [e.event_type for e in events]
    assert kinds.count("YIELD") == 2, kinds
    assert kinds[-1] == "COMPLETED", f"no COMPLETED delivered, got {kinds}"


@pytest.mark.asyncio
async def test_a_raising_task_delivers_critical_over_the_websocket(tmp_path: Path) -> None:
    async with AsyncAgentTestClient(_build_app(tmp_path), as_user="tester") as client:
        result = await client.assign("explode", {})
        events = await client.collect_until_error(result.task_id, timeout=5)

    kinds = [e.event_type for e in events]
    assert kinds and kinds[-1] == "CRITICAL", f"no CRITICAL delivered, got {kinds}"
