"""FastAPI integration for rekuest_next agents."""

from .routes import (
    add_agent_routes,
    add_implementation_routes,
    add_lock_routes,
    add_schema_routes,
    add_state_detail_routes,
    add_state_routes,
    configure_fastapi,
    create_lifespan,
)
from .testing import (
    AsyncAgentTestClient,
    AgentTestClient,
    AssignmentResult,
    BufferedEvent,
    create_test_app_and_agent,
)
from .agent import FastAPIConnectionManager, FastApiAgent, FastApiTransport


__all__ = [
    "FastApiAgent",
    "FastApiTransport",
    "FastAPIConnectionManager",
    "configure_fastapi",
    "create_lifespan",
    "add_agent_routes",
    "add_implementation_routes",
    "add_lock_routes",
    "add_schema_routes",
    "add_state_detail_routes",
    "add_state_routes",
    # Testing utilities
    "AgentTestClient",
    "AsyncAgentTestClient",
    "AssignmentResult",
    "BufferedEvent",
    "create_test_app_and_agent",
]
