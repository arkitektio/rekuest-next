"""Integration tests for cross-app dependencies (``declare`` + ``register``).

These tests stand up several independent ``RekuestNext`` apps (each with its own
fresh ``AppRegistry`` and unique instance id, via :func:`build_fresh_rekuest`)
against the shared docker deployment. One app registers a plain action, another
registers a "workflow" action that ``declare``s a dependency on the first app's
protocol and calls it through the injected proxy.

This exercises the full end-to-end dependency-resolution path over the real
transport: the workflow's declared dependency must be resolved by the server to
the live provider agent, and the proxied method call (``acall_dependency``) must
round-trip to that agent.
"""

import asyncio
from typing import Protocol

import pytest
from dokker import Deployment

from rekuest_next.api.schema import amy_implementation_at
from rekuest_next.declare import declare
from rekuest_next.remote import acall

from .conftest import build_fresh_rekuest


@pytest.mark.integration
@pytest.mark.asyncio(scope="session")
async def test_single_app_with_app_token(deployment: Deployment) -> None:
    """Sanity check: one app authenticating with a non-default app token.

    Confirms the dedicated ``atest_token`` static token provisions a valid app
    and that its single registered action is callable.
    """

    provider = build_fresh_rekuest(
        deployment, instance_id="atest-provider", token="atest_token"
    )

    def do_stuff(printer: str) -> str:
        """Stitch a list of images."""
        return "stitched-" + printer

    provider.register(do_stuff)

    async with provider as provider:
        task = asyncio.create_task(provider.arun())
        await asyncio.sleep(5)

        impl = await amy_implementation_at(provider.agent.instance_id, "do_stuff")
        answer = await acall(impl, printer="x")
        assert answer == "stitched-x", f"Unexpected result: {answer!r}"

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@pytest.mark.integration
@pytest.mark.asyncio(scope="session")
async def test_workflow_calls_single_dependency(deployment: Deployment) -> None:
    """A workflow app resolves and calls a single declared dependency.

    Minimal de-risk case: one provider app exposing ``do_stuff`` and one
    workflow app that declares a dependency on it and calls it.
    """

    # --- Provider app: registers the concrete implementation -----------------
    provider = build_fresh_rekuest(
        deployment, instance_id="atest-provider", token="atest_token"
    )

    def do_stuff(printer: str) -> str:
        """Stitch a list of images."""
        return "stitched-" + printer

    provider.register(do_stuff)

    # --- Workflow app: declares a dependency on the provider's protocol ------
    workflow_app = build_fresh_rekuest(
        deployment, instance_id="workflow", token="workflow_token"
    )

    @declare(app="atest", auto_resolvable=True, min=1)
    class ATestLike(Protocol):
        def do_stuff(self, printer: str) -> str:
            """Stitch a list of images."""
            ...

    def single_workflow(atest: ATestLike) -> str:
        """Call the declared atest dependency and return its result."""
        return atest.do_stuff("printer")

    workflow_app.register(single_workflow)

    async with provider as provider, workflow_app as workflow_app:
        # Start the provider first and let it fully register before the workflow
        # connects. All the static tokens map to the same user (``sub: 1`` ->
        # ``lok_1``), so starting both agents at once races on first-time user
        # creation; staggering the starts lets the user be created exactly once.
        provider_task = asyncio.create_task(provider.arun())
        await asyncio.sleep(5)
        workflow_task = asyncio.create_task(workflow_app.arun())
        await asyncio.sleep(5)

        # With two apps entered, the ambient rath/postman context is ambiguous,
        # so address every remote call explicitly to the workflow app.
        impl = await amy_implementation_at(
            workflow_app.agent.instance_id,
            "single_workflow",
            rath=workflow_app.rath,
        )

        answer = await acall(
            impl,
            postman=workflow_app.postman,
            structure_registry=workflow_app.structure_registry,
        )
        assert answer == "stitched-printer", f"Unexpected workflow result: {answer!r}"

        for task in (provider_task, workflow_task):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


@pytest.mark.integration
@pytest.mark.asyncio(scope="session")
async def test_workflow_calls_two_separate_apps(deployment: Deployment) -> None:
    """A workflow app calls two independent provider apps via declared deps.

    This is the full scenario: two genuinely separate apps (``atest`` exposing
    ``do_stuff`` and ``btest`` exposing ``do_another_stuff``) plus a third
    workflow app that declares a dependency on each and composes their results.
    """

    # --- Provider app A: atest -----------------------------------------------
    atest_app = build_fresh_rekuest(
        deployment, instance_id="atest-provider", token="atest_token"
    )

    def do_stuff(printer: str) -> str:
        """Stitch a list of images."""
        return "stitched-" + printer

    atest_app.register(do_stuff)

    # --- Provider app B: btest -----------------------------------------------
    btest_app = build_fresh_rekuest(
        deployment, instance_id="btest-provider", token="btest_token"
    )

    def do_another_stuff(ptiner: str) -> str:
        """Segment an image."""
        return "segmented-" + ptiner

    btest_app.register(do_another_stuff)

    # --- Workflow app: depends on both providers -----------------------------
    workflow_app = build_fresh_rekuest(
        deployment, instance_id="workflow", token="workflow_token"
    )

    @declare(app="atest", auto_resolvable=True, min=1)
    class ATestLike(Protocol):
        def do_stuff(self, printer: str) -> str:
            """Stitch a list of images."""
            ...

    @declare(app="btest", auto_resolvable=True, min=1)
    class BTestLike(Protocol):
        def do_another_stuff(self, ptiner: str) -> str:
            """Segment an image."""
            ...

    def two_app_workflow(atest: ATestLike, btest: BTestLike) -> str:
        """Compose the results of both declared dependencies."""
        return atest.do_stuff("printer") + "|" + btest.do_another_stuff("ptiner")

    workflow_app.register(two_app_workflow)

    async with (
        atest_app as atest_app,
        btest_app as btest_app,
        workflow_app as workflow_app,
    ):
        # Stagger the agent starts: all tokens map to the same user (``sub: 1``),
        # so launching together races on first-time user creation. Start each
        # provider in turn, then the workflow that depends on them.
        atest_task = asyncio.create_task(atest_app.arun())
        await asyncio.sleep(4)
        btest_task = asyncio.create_task(btest_app.arun())
        await asyncio.sleep(4)
        workflow_task = asyncio.create_task(workflow_app.arun())
        # Let all three agents fully settle. Each new agent for the same user
        # briefly churns the others' registrations, so wait until things are
        # stable before asking the server to resolve the dependencies.
        await asyncio.sleep(10)

        # Address every remote call explicitly to the workflow app, since the
        # ambient rath/postman context is ambiguous with three apps entered.
        impl = await amy_implementation_at(
            workflow_app.agent.instance_id,
            "two_app_workflow",
            rath=workflow_app.rath,
        )

        answer = await acall(
            impl,
            postman=workflow_app.postman,
            structure_registry=workflow_app.structure_registry,
        )
        assert answer == "stitched-printer|segmented-ptiner", (
            f"Unexpected workflow result: {answer!r}"
        )

        for task in (atest_task, btest_task, workflow_task):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


@pytest.mark.integration
@pytest.mark.asyncio(scope="session")
async def test_workflow_calls_two_separate_apps_async(deployment: Deployment) -> None:
    """A workflow app calls two independent provider apps via declared deps.

    This is the full scenario: two genuinely separate apps (``atest`` exposing
    ``do_stuff`` and ``btest`` exposing ``do_another_stuff``) plus a third
    workflow app that declares a dependency on each and composes their results.
    """

    # --- Provider app A: atest -----------------------------------------------
    atest_app = build_fresh_rekuest(
        deployment, instance_id="atest-provider", token="atest_token"
    )

    def do_stuff(printer: str) -> str:
        """Stitch a list of images."""
        return "stitched-" + printer

    atest_app.register(do_stuff)

    # --- Provider app B: btest -----------------------------------------------
    btest_app = build_fresh_rekuest(
        deployment, instance_id="btest-provider", token="btest_token"
    )

    def do_another_stuff(ptiner: str) -> str:
        """Segment an image."""
        return "segmented-" + ptiner

    btest_app.register(do_another_stuff)

    # --- Workflow app: depends on both providers -----------------------------
    workflow_app = build_fresh_rekuest(
        deployment, instance_id="workflow", token="workflow_token"
    )

    @declare(app="atest", auto_resolvable=True, min=1)
    class ATestLike(Protocol):
        async def do_stuff(self, printer: str) -> str:
            """Stitch a list of images."""
            ...

    @declare(app="btest", auto_resolvable=True, min=1)
    class BTestLike(Protocol):
        async def do_another_stuff(self, ptiner: str) -> str:
            """Segment an image."""
            ...

    async def two_app_workflow(atest: ATestLike, btest: BTestLike) -> str:
        """Compose the results of both declared dependencies."""
        return (
            await atest.do_stuff("printer")
            + "|"
            + await btest.do_another_stuff("ptiner")
        )

    workflow_app.register(two_app_workflow)

    async with (
        atest_app as atest_app,
        btest_app as btest_app,
        workflow_app as workflow_app,
    ):
        # Stagger the agent starts: all tokens map to the same user (``sub: 1``),
        # so launching together races on first-time user creation. Start each
        # provider in turn, then the workflow that depends on them.
        atest_task = asyncio.create_task(atest_app.arun())
        await asyncio.sleep(4)
        btest_task = asyncio.create_task(btest_app.arun())
        await asyncio.sleep(4)
        workflow_task = asyncio.create_task(workflow_app.arun())
        # Let all three agents fully settle. Each new agent for the same user
        # briefly churns the others' registrations, so wait until things are
        # stable before asking the server to resolve the dependencies.
        await asyncio.sleep(10)

        # Address every remote call explicitly to the workflow app, since the
        # ambient rath/postman context is ambiguous with three apps entered.
        impl = await amy_implementation_at(
            workflow_app.agent.instance_id,
            "two_app_workflow",
            rath=workflow_app.rath,
        )

        answer = await acall(
            impl,
            postman=workflow_app.postman,
            structure_registry=workflow_app.structure_registry,
        )
        assert answer == "stitched-printer|segmented-ptiner", (
            f"Unexpected workflow result: {answer!r}"
        )

        for task in (atest_task, btest_task, workflow_task):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
