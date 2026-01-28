"""FastAPI integration for rekuest_next agents."""

from .agent import FastApiAgent, FastApiTransport, FastAPIConnectionManager
from .routes import (
    configure_fastapi,
    create_lifespan,
    add_agent_routes,
    add_implementation_routes,
    add_implementation_route,
    add_state_routes,
    add_state_route,
    configure_openapi,
)
from .testing import (
    AgentTestClient,
    AsyncAgentTestClient,
    AssignmentResult,
    BufferedEvent,
    create_test_app_and_agent,
)

__all__ = [
    "FastApiAgent",
    "FastApiTransport",
    "FastAPIConnectionManager",
    "configure_fastapi",
    "create_lifespan",
    "add_agent_routes",
    "add_implementation_routes",
    "add_implementation_route",
    "add_state_routes",
    "add_state_route",
    "configure_openapi",
    # Testing utilities
    "AgentTestClient",
    "AsyncAgentTestClient",
    "AssignmentResult",
    "BufferedEvent",
    "create_test_app_and_agent",
]
