"""Integration test: actor-internal calls are delegated to the agent socket.

When an action body calls a *declared dependency* (or another action), the call should
travel over the **agent's own WebSocket** as an ``AssignRequest`` instead of going out
through the GraphQL postman. This mirrors ``test_app_dependencies`` but additionally proves
the inner call went through the :class:`~rekuest_next.agents.caller.AgentPostman` (the agent
caller) rather than the GraphQL postman.

The standalone / human-induced path (a caller *outside* any actor) keeps using the GraphQL
postman — that is what kicks off the outer ``single_workflow`` task here.

NOTE: like the rest of the integration suite this needs the docker deployment (``deployment``
fixture) and a working executor path.
"""

import asyncio
from typing import List, Protocol

import pytest
from dokker import Deployment

from rekuest_next.agents.caller import AgentPostman
from rekuest_next.api.schema import AssignInput, amy_implementation_at
from rekuest_next.declare import declare
from rekuest_next.remote import acall

from .conftest import CONNECT_TIMEOUT, build_fresh_rekuest


@pytest.mark.integration
@pytest.mark.asyncio(scope="session")
async def test_actor_internal_dependency_call_uses_agent(
    deployment: Deployment, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dependency called from inside an actor routes over the agent socket.

    Asserts both that the value round-trips and that the inner call went through
    ``AgentPostman.aassign`` (the agent caller) — not the GraphQL postman.
    """

    delegated: List[AssignInput] = []
    original_aassign = AgentPostman.aassign

    def spy_aassign(self: AgentPostman, assign: AssignInput):
        delegated.append(assign)
        return original_aassign(self, assign)

    monkeypatch.setattr(AgentPostman, "aassign", spy_aassign)

    # --- Provider app: registers the concrete implementation -----------------
    provider = build_fresh_rekuest(deployment, token="atest_token")

    def do_stuff(printer: str) -> str:
        """Stitch a list of images."""
        return "stitched-" + printer

    provider.register(do_stuff)

    # --- Workflow app: declares a dependency and calls it from inside an actor
    workflow_app = build_fresh_rekuest(deployment, token="workflow_token")

    @declare(app="atest", auto_resolvable=True, min=1)
    class ATestLike(Protocol):
        def do_stuff(self, printer: str) -> str:
            """Stitch a list of images."""
            ...

    def single_workflow(atest: ATestLike) -> str:
        """Call the declared atest dependency (this travels over the agent socket)."""
        return atest.do_stuff("printer")

    workflow_app.register(single_workflow)

    async with provider as provider, workflow_app as workflow_app:
        await provider.aconnect(timeout=CONNECT_TIMEOUT)
        provider_task = asyncio.create_task(provider.aloop())
        await workflow_app.aconnect(timeout=CONNECT_TIMEOUT)
        workflow_task = asyncio.create_task(workflow_app.aloop())

        # The OUTER assign (human-induced) goes through the GraphQL postman.
        impl = await amy_implementation_at(
            "single_workflow",
            rath=workflow_app.rath,
        )
        answer = await acall(
            impl,
            postman=workflow_app.postman,
            structure_registry=workflow_app.structure_registry,
        )

        assert answer == "stitched-printer", f"Unexpected workflow result: {answer!r}"
        # The INNER dependency call must have been delegated to the agent caller.
        assert delegated, "the dependency call did not go through the agent caller postman"
        assert any(a.dependency is not None for a in delegated), (
            "expected a dependency-resolving AssignRequest over the agent socket"
        )

        for task in (provider_task, workflow_task):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
