"""General Tests for defininin actions"""

import asyncio
import time
from rekuest_next.api.schema import (
    acreate_implementation,
    create_implementation,
    ImplementationInput,
    amy_implementation_at,
)
import pytest
from rekuest_next.definition.define import prepare_definition
from rekuest_next.structures.registry import StructureRegistry
from .funcs import (
    nested_basic_function,
)
from .annotated_funcs import annotated_x, annotated_choice_x
from .conftest import DeployedRekuest
from rekuest_next.remote import acall
from rekuest_next.declare import agent_protocol, protocol


@agent_protocol
class NecessaryProtocol:
    def necessary_protocol(number: int) -> int: ...


def a_function(a: int) -> int:
    return necessary_protocol(a) + 1


@pytest.mark.integration
@pytest.mark.asyncio(scope="session")
async def test_run_and_cancel_app(
    simple_registry: StructureRegistry, async_deployed_app: DeployedRekuest
) -> None:
    """Test if the hases of to equal definitions are the same."""
    """Test if the hases of to equal definitions are the same."""
    async_deployed_app.rekuest.register(a_function, dependencies=[NecessaryProtocol])

    task = asyncio.create_task(async_deployed_app.rekuest.arun())

    await asyncio.sleep(5)  # Wait for the app to start

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
