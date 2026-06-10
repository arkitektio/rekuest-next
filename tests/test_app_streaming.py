"""Integration tests for streaming (generator) actions.

Each test stands up its own ``RekuestNext`` with a fresh ``AppRegistry``
(via :func:`build_fresh_rekuest`) against the shared deployment, registers a
generator function, runs the agent, and consumes the yields with ``aiterate``.
This exercises the per-yield shrink → YieldEvent pipeline of the generator
actors (both the threaded sync-generator and the async-generator variants)
over the real transport.
"""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
from dokker import Deployment

from rekuest_next.api.schema import amy_implementation_at
from rekuest_next.remote import aiterate

from .conftest import build_fresh_rekuest


@pytest.mark.integration
@pytest.mark.asyncio(scope="session")
async def test_iterate_sync_generator_action(deployment: Deployment) -> None:
    """A sync generator action streams each yield to the caller."""

    app = build_fresh_rekuest(deployment)

    def count_up(until: int) -> Generator[int, None, None]:
        """Count up to a number, yielding each value."""
        for i in range(until):
            yield i

    app.register(count_up)

    async with app as app:
        task = asyncio.create_task(app.arun())
        await asyncio.sleep(5)  # Wait for the agent to provide

        impl = await amy_implementation_at(app.agent.instance_id, "count_up")

        received = [value async for value in aiterate(impl, until=3)]
        assert received == [0, 1, 2], f"Expected streamed [0, 1, 2], got {received}"

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@pytest.mark.integration
@pytest.mark.asyncio(scope="session")
async def test_iterate_async_generator_action(deployment: Deployment) -> None:
    """An async generator action streams each yield to the caller."""

    app = build_fresh_rekuest(deployment)

    async def spell_out(word: str) -> AsyncGenerator[str, None]:
        """Yield each character of a word."""
        for char in word:
            yield char

    app.register(spell_out)

    async with app as app:
        task = asyncio.create_task(app.arun())
        await asyncio.sleep(5)  # Wait for the agent to provide

        impl = await amy_implementation_at(app.agent.instance_id, "spell_out")

        received = [value async for value in aiterate(impl, word="abc")]
        assert received == ["a", "b", "c"], f"Expected ['a', 'b', 'c'], got {received}"

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
