"""FastAPI integration for rekuest_next agents."""

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


def __getattr__(name: str):
    if name in {"FastApiAgent", "FastApiTransport", "FastAPIConnectionManager"}:
        from .agent import FastAPIConnectionManager, FastApiAgent, FastApiTransport

        return {
            "FastApiAgent": FastApiAgent,
            "FastApiTransport": FastApiTransport,
            "FastAPIConnectionManager": FastAPIConnectionManager,
        }[name]

    if name in {
        "configure_fastapi",
        "create_lifespan",
        "add_agent_routes",
        "add_implementation_routes",
        "add_state_routes",
    }:
        from .routes import (
            add_agent_routes,
            add_implementation_routes,
            add_state_routes,
            configure_fastapi,
            create_lifespan,
        )

        return {
            "configure_fastapi": configure_fastapi,
            "create_lifespan": create_lifespan,
            "add_agent_routes": add_agent_routes,
            "add_implementation_routes": add_implementation_routes,
            "add_state_routes": add_state_routes,
        }[name]

    if name in {
        "AgentTestClient",
        "AsyncAgentTestClient",
        "AssignmentResult",
        "BufferedEvent",
        "create_test_app_and_agent",
    }:
        from .testing import (
            AgentTestClient,
            AsyncAgentTestClient,
            AssignmentResult,
            BufferedEvent,
            create_test_app_and_agent,
        )

        return {
            "AgentTestClient": AgentTestClient,
            "AsyncAgentTestClient": AsyncAgentTestClient,
            "AssignmentResult": AssignmentResult,
            "BufferedEvent": BufferedEvent,
            "create_test_app_and_agent": create_test_app_and_agent,
        }[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
