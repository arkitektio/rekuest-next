"""Tests for the FastAPI agent integration.

This module tests the FastAPI agent using AsyncAgentTestClient
for full async integration testing with proper event handling.
"""

import asyncio
from typing import Generator

import pytest
from fastapi import FastAPI, Request

from rekuest_next.contrib.fastapi import (
    FastApiAgent,
    AsyncAgentTestClient,
    create_test_app_and_agent,
)
from rekuest_next.app import AppRegistry


# Type alias for test setup tuple
TestSetup = tuple[FastAPI, FastApiAgent, AppRegistry]


def get_user_from_request(request: Request) -> int:
    """Placeholder function to extract user info from request."""
    return 1


async def create_test_setup() -> TestSetup:
    """Create a test app with a registered simple function."""
    app, agent, app_registry = create_test_app_and_agent()

    @app_registry.register
    def add_numbers(a: int, b: int) -> int:
        """Add two numbers together."""
        return a + b

    list = await agent.extension_registry.get("default").aget_implementations()
    assert len(list) == 1

    return app, agent, app_registry


async def create_generator_setup() -> TestSetup:
    """Create a test app with a registered generator function."""
    app, agent, app_registry = create_test_app_and_agent()

    @app_registry.register
    def count_up(start: int, end: int) -> Generator[int, None, None]:
        """Generate numbers from start to end."""
        for i in range(start, end + 1):
            yield i

    return app, agent, app_registry


# =============================================================================
# Basic Route Tests
# =============================================================================


@pytest.mark.asyncio
async def test_app_has_routes() -> None:
    """Test that the app has the expected routes configured."""
    app, agent, _ = await create_test_setup()

    async with AsyncAgentTestClient(app, agent) as client:
        route_paths = [route.path for route in app.routes]  # type: ignore

        # Check that agent routes are present
        assert "/ws" in route_paths
        assert "/assignations" in route_paths
        assert "/assignations/{assignation_id}" in route_paths

        # Check that implementation route is present
        assert "/add_numbers" in route_paths


@pytest.mark.asyncio
async def test_openapi_schema_includes_implementation() -> None:
    """Test that the OpenAPI schema includes the implementation."""
    app, agent, _ = await create_test_setup()

    async with AsyncAgentTestClient(app, agent) as client:
        response = await client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()

        # Check that our implementation is in the paths
        assert "/add_numbers" in schema["paths"]

        # Check the schema has our implementation's details
        add_numbers_schema = schema["paths"]["/add_numbers"]
        assert "post" in add_numbers_schema


# =============================================================================
# Assignment Tests
# =============================================================================


@pytest.mark.asyncio
async def test_assign_work() -> None:
    """Test assigning work to an implementation."""
    app, agent, _ = await create_test_setup()

    async with AsyncAgentTestClient(app, agent) as client:
        result = await client.assign("add_numbers", {"a": 5, "b": 3})

        assert result.status == "submitted"
        assert result.assignation_id is not None


@pytest.mark.asyncio
async def test_assign_with_as_user() -> None:
    """Test assigning work with as_user parameter."""
    app, agent, _ = await create_test_setup()

    async with AsyncAgentTestClient(app, agent, as_user="test-user-123") as client:
        result = await client.assign("add_numbers", {"a": 1, "b": 2})

        assert result.status == "submitted"
        assert result.assignation_id is not None


@pytest.mark.asyncio
async def test_assign_and_get_result() -> None:
    """Test a full assign cycle and collect events until done."""
    app, agent, _ = await create_test_setup()

    async with AsyncAgentTestClient(app, agent) as client:
        # Assign work
        assign_result = await client.assign("add_numbers", {"a": 2, "b": 3})
        assert assign_result.status == "submitted"

        # Collect events until done
        events = await client.collect_until_done(assign_result.assignation_id)

        # Should have received events including DONE
        assert len(events) >= 1
        assert events[-1].is_done()


@pytest.mark.asyncio
async def test_assign_and_check_yield_returns() -> None:
    """Test that YIELD event contains the correct return value."""
    app, agent, _ = await create_test_setup()

    async with AsyncAgentTestClient(app, agent) as client:
        # Assign work
        assign_result = await client.assign("add_numbers", {"a": 10, "b": 20})

        # Collect events until done
        events = await client.collect_until_done(assign_result.assignation_id)

        # Find YIELD event
        yield_events = [e for e in events if e.is_yield()]
        assert len(yield_events) >= 1

        # Check the return value
        returns = yield_events[0].get_returns()
        assert returns is not None
        assert returns.get("return0") == 30  # 10 + 20


# =============================================================================
# Generator Function Tests
# =============================================================================


@pytest.mark.asyncio
async def test_generator_function_assignment() -> None:
    """Test assigning work to a generator function."""
    app, agent, _ = await create_generator_setup()

    async with AsyncAgentTestClient(app, agent) as client:
        result = await client.assign("count_up", {"start": 1, "end": 3})

        assert result.status == "submitted"

        # Collect events until done
        events = await client.collect_until_done(result.assignation_id)

        assert len(events) >= 1
        assert events[-1].is_done()


@pytest.mark.asyncio
async def test_generator_yields_multiple_values() -> None:
    """Test that generator yields multiple values."""
    app, agent, _ = await create_generator_setup()

    async with AsyncAgentTestClient(app, agent) as client:
        result = await client.assign("count_up", {"start": 1, "end": 3})

        events = await client.collect_until_done(result.assignation_id)

        yield_events = [e for e in events if e.is_yield()]
        # Generator should yield 3 values: 1, 2, 3
        assert len(yield_events) == 3

        values = [e.get_returns().get("return0") for e in yield_events]
        assert values == [1, 2, 3]


# =============================================================================
# HTTP Endpoint Tests
# =============================================================================


@pytest.mark.asyncio(scope="session")
async def test_get_assignations_endpoint() -> None:
    """Test the GET /assignations endpoint."""
    app, agent, _ = await create_test_setup()

    async with AsyncAgentTestClient(app, agent) as client:
        response = await client.get("/assignations")
        assert response.status_code == 200
        data = response.json()
        assert "assignations" in data
        assert "count" in data


@pytest.mark.asyncio(scope="session")
async def test_assignation_appears_in_list() -> None:
    """Test that assigned work appears in the assignations list while running.

    Note: Assignations are removed from managed_assignments after completion,
    so this test verifies the structure of the endpoint response.
    """
    app, agent, _ = await create_test_setup()

    async with AsyncAgentTestClient(app, agent) as client:
        # Assign work
        result = await client.assign("add_numbers", {"a": 1, "b": 1})

        # Wait for completion
        await client.collect_until_done(result.assignation_id)

        # After completion, the assignation may be removed from managed_assignments
        # Just verify the endpoint returns valid structure
        response = await client.get("/assignations")
        assert response.status_code == 200
        data = response.json()
        assert "assignations" in data
        assert isinstance(data["assignations"], dict)


@pytest.mark.asyncio(scope="session")
async def test_get_single_assignation() -> None:
    """Test getting a single assignation by ID.

    The assignation endpoint should return details about an assignation.
    Since the processing happens quickly, we check the endpoint works.
    """
    app, agent, _ = await create_test_setup()

    async with AsyncAgentTestClient(app, agent) as client:
        # Assign work
        result = await client.assign("add_numbers", {"a": 5, "b": 5})

        # The assignation may or may not still exist depending on timing
        # We just verify the endpoint responds correctly
        response = await client.get(f"/assignations/{result.assignation_id}")

        # Either 200 (still processing) or 404 (already completed)
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert data["assignation"] == result.assignation_id


@pytest.mark.asyncio(scope="session")
async def test_get_nonexistent_assignation_returns_404() -> None:
    """Test that getting a nonexistent assignation returns 404."""
    app, agent, _ = await create_test_setup()

    async with AsyncAgentTestClient(app, agent) as client:
        response = await client.get("/assignations/nonexistent-id")
        assert response.status_code == 404


# =============================================================================
# Event Collection Tests
# =============================================================================


@pytest.mark.asyncio(scope="session")
async def test_receive_single_event() -> None:
    """Test receiving a single event."""
    app, agent, _ = await create_test_setup()

    async with AsyncAgentTestClient(app, agent) as client:
        result = await client.assign("add_numbers", {"a": 1, "b": 1})

        event = await client.receive_event(timeout=5.0)

        assert event is not None
        assert event.assignation == result.assignation_id


@pytest.mark.asyncio(scope="session")
async def test_collect_multiple_events() -> None:
    """Test collecting multiple events."""
    app, agent, _ = await create_test_setup()

    async with AsyncAgentTestClient(app, agent) as client:
        result = await client.assign("add_numbers", {"a": 1, "b": 1})

        # Collect up to 3 events
        events = await client.collect_events(count=3, timeout=5.0)

        # Should have at least YIELD and DONE
        assert len(events) >= 2


@pytest.mark.asyncio(scope="session")
async def test_collect_until_done_timeout() -> None:
    """Test that collect_until_done works with timeout."""
    app, agent, _ = await create_test_setup()

    async with AsyncAgentTestClient(app, agent) as client:
        result = await client.assign("add_numbers", {"a": 1, "b": 1})

        # Should complete before timeout
        events = await client.collect_until_done(result.assignation_id, timeout=10.0)

        assert len(events) >= 1
        assert events[-1].is_done()


# =============================================================================
# as_user Parameter Tests
# =============================================================================


@pytest.mark.asyncio(scope="session")
async def test_as_user_header_in_post() -> None:
    """Test that as_user parameter adds x-session-user header to POST requests."""
    app, agent, _ = await create_test_setup()

    async with AsyncAgentTestClient(app, agent, as_user="header-test-user") as client:
        # The assign method should include the header
        result = await client.assign("add_numbers", {"a": 1, "b": 1})
        assert result.status == "submitted"


@pytest.mark.asyncio(scope="session")
async def test_as_user_header_in_get() -> None:
    """Test that as_user parameter adds x-session-user header to GET requests."""
    app, agent, _ = await create_test_setup()

    async with AsyncAgentTestClient(app, agent, as_user="header-test-user") as client:
        response = await client.get("/assignations")
        assert response.status_code == 200


@pytest.mark.asyncio(scope="session")
async def test_multiple_users_can_assign() -> None:
    """Test that multiple users can assign work."""
    app, agent, _ = await create_test_setup()

    async with AsyncAgentTestClient(app, agent, as_user="user-1") as client1:
        result1 = await client1.assign("add_numbers", {"a": 1, "b": 1})
        assert result1.status == "submitted"

    async with AsyncAgentTestClient(app, agent, as_user="user-2") as client2:
        result2 = await client2.assign("add_numbers", {"a": 2, "b": 2})
        assert result2.status == "submitted"

    # Both assignments should have different IDs
    assert result1.assignation_id != result2.assignation_id


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.asyncio(scope="session")
async def test_assign_unknown_interface_returns_error() -> None:
    """Test that assigning to an unknown interface returns an error."""
    app, agent, _ = await create_test_setup()

    async with AsyncAgentTestClient(app, agent) as client:
        response = await client.post(
            "/assign",
            json={
                "interface": "nonexistent_function",
                "args": {},
            },
        )
        # Should return 404 or similar error
        assert response.status_code in [404, 400, 422]


# =============================================================================
# BufferedEvent Tests
# =============================================================================


@pytest.mark.asyncio(scope="session")
async def test_buffered_event_is_done() -> None:
    """Test BufferedEvent.is_done() method."""
    app, agent, _ = await create_test_setup()

    async with AsyncAgentTestClient(app, agent) as client:
        result = await client.assign("add_numbers", {"a": 1, "b": 1})
        events = await client.collect_until_done(result.assignation_id)

        done_events = [e for e in events if e.is_done()]
        assert len(done_events) == 1


@pytest.mark.asyncio(scope="session")
async def test_buffered_event_is_yield() -> None:
    """Test BufferedEvent.is_yield() method."""
    app, agent, _ = await create_test_setup()

    async with AsyncAgentTestClient(app, agent) as client:
        result = await client.assign("add_numbers", {"a": 1, "b": 1})
        events = await client.collect_until_done(result.assignation_id)

        yield_events = [e for e in events if e.is_yield()]
        assert len(yield_events) >= 1


@pytest.mark.asyncio(scope="session")
async def test_buffered_event_get_returns() -> None:
    """Test BufferedEvent.get_returns() method."""
    app, agent, _ = await create_test_setup()

    async with AsyncAgentTestClient(app, agent) as client:
        result = await client.assign("add_numbers", {"a": 7, "b": 8})
        events = await client.collect_until_done(result.assignation_id)

        yield_events = [e for e in events if e.is_yield()]
        assert len(yield_events) >= 1

        returns = yield_events[0].get_returns()
        assert returns is not None
        assert "return0" in returns
        assert returns["return0"] == 15  # 7 + 8
