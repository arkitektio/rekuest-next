"""FastAPI integration for rekuest_next agents."""

from .agent import (
    FastAPIConnectionManager,
    FastApiAgent,
    FastApiTransport,
)
from .routes import (
    configure_fastapi,
    create_lifespan,
    add_agent_routes,
    add_implementation_routes,
    add_state_routes,
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
    "add_state_routes",
    # Testing utilities
    "AgentTestClient",
    "AsyncAgentTestClient",
    "AssignmentResult",
    "BufferedEvent",
    "create_test_app_and_agent",
]
