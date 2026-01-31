"""General Tests for defininin actions"""

import asyncio
from rekuest_next.api.schema import (
    amy_implementation_at,
)
import pytest
from rekuest_next.structures.registry import StructureRegistry
from .conftest import DeployedRekuest
from rekuest_next.remote import acall


@pytest.mark.integration
@pytest.mark.asyncio(scope="session")
async def test_run_and_cancel_app(
    simple_registry: StructureRegistry, async_deployed_app: DeployedRekuest
) -> None:
    """Test if the hases of to equal definitions are the same."""
    """Test if the hases of to equal definitions are the same."""

    task = asyncio.create_task(async_deployed_app.rekuest.arun())

    await asyncio.sleep(3)  # Wait for the app to start

    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.integration
@pytest.mark.asyncio(scope="session")
async def test_run_and_call_app(
    simple_registry: StructureRegistry, async_deployed_app: DeployedRekuest
) -> None:
    """Test if the hases of to equal definitions are the same."""
    """Test if the hases of to equal definitions are the same."""

    task = asyncio.create_task(async_deployed_app.rekuest.arun())

    await asyncio.sleep(5)  # Wait for the app to start

    impl = await amy_implementation_at(async_deployed_app.instance_id, "most_basic_function")

    answer = await acall(impl, hello="hello")
    assert answer == "hello world", "The answer should be 'hello'"

    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass
