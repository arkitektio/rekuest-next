"""Some configuration for pytest"""

import pytest
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.rekuest import RekuestNext, RekuestNextRath
from rekuest_next.rath import RekuestNextRath
from rath.links.testing.direct_succeeding_link import DirectSucceedingLink
from rekuest_next.agents.base import BaseAgent
from rekuest_next.postmans.graphql import GraphQLPostman
from rekuest_next.agents.transport.websocket import WebsocketAgentTransport


class MockShelver:
    """A mock shelver that stores values in memory. This is used to test the
    shelver functionality without using a real shelver."""

    def __init__(self) -> None:
        """Initialize the mock shelver."""
        self.shelve = {}

    async def aput_on_shelve(self, identifier: str, value: object) -> str:
        """Put a value on the shelve and return the key. This is used to store
        values on the shelve."""
        key = str(id(value))
        self.shelve[key] = value
        return key

    async def aget_from_shelve(self, key: str) -> object:
        """Get a value from the shelve. This is used to get values from the
        shelve."""
        return self.shelve[key]


@pytest.fixture()
def simple_registry() -> StructureRegistry:
    """Fixture for a simple registry"""
    registry = StructureRegistry()

    return registry


@pytest.fixture()
def mock_shelver() -> MockShelver:
    """Fixture for a mock shelver"""
    return MockShelver()


@pytest.fixture()
def mock_rekuest() -> None:
    """Fixture for a mock rekuest"""
    # This fixture can be used to mock the rekuest functionality if needed

    instance_id = "default"

    async def token_loader() -> str:
        """Mock token loader function."""
        return "mock_token"

    rath = RekuestNextRath(link=DirectSucceedingLink())

    agent = BaseAgent(
        transport=WebsocketAgentTransport(
            endpoint_url="ws://localhost:8000/graphql",
            token_loader=token_loader,
        ),
        instance_id=instance_id,
        rath=rath,
        name=f"Test",
    )

    rath = RekuestNextRath(link=DirectSucceedingLink())

    x = RekuestNext(
        rath=rath,
        agent=agent,
        postman=GraphQLPostman(
            rath=rath,
            instance_id=instance_id,
        ),
    )

    return x
