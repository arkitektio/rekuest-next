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
import threading
import time
from typing import Protocol

import pytest
from dokker import Deployment
from koil import check_cancelled
from koil.errors import ThreadCancelledError

from rekuest_next.api.schema import amy_implementation_at
from rekuest_next.declare import declare
from rekuest_next.remote import acall

from .conftest import CONNECT_TIMEOUT, build_fresh_rekuest


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_single_app_with_app_token(deployment: Deployment) -> None:
    """Sanity check: one app authenticating with a non-default app token.

    Confirms the dedicated ``atest_token`` static token provisions a valid app
    and that its single registered action is callable.
    """

    provider = build_fresh_rekuest(
        deployment, token="atest_token"
    )

    def do_stuff(printer: str) -> str:
        """Stitch a list of images."""
        return "stitched-" + printer

    provider.register(do_stuff)

    async with provider as provider:
        await provider.aconnect(timeout=CONNECT_TIMEOUT)
        task = asyncio.create_task(provider.aloop())

        impl = await amy_implementation_at("do_stuff")
        answer = await acall(impl, printer="x")
        assert answer == "stitched-x", f"Unexpected result: {answer!r}"

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_workflow_calls_single_dependency(deployment: Deployment) -> None:
    """A workflow app resolves and calls a single declared dependency.

    Minimal de-risk case: one provider app exposing ``do_stuff`` and one
    workflow app that declares a dependency on it and calls it.
    """

    # --- Provider app: registers the concrete implementation -----------------
    provider = build_fresh_rekuest(
        deployment, token="atest_token"
    )

    def do_stuff(printer: str) -> str:
        """Stitch a list of images."""
        return "stitched-" + printer

    provider.register(do_stuff)

    # --- Workflow app: declares a dependency on the provider's protocol ------
    workflow_app = build_fresh_rekuest(
        deployment, token="workflow_token"
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
        # Connect the provider first and let it be fully acknowledged before the
        # workflow connects, so the workflow's dependency resolves to a live
        # provider. Awaiting each ``aconnect`` makes that ordering deterministic.
        await provider.aconnect(timeout=CONNECT_TIMEOUT)
        provider_task = asyncio.create_task(provider.aloop())
        await workflow_app.aconnect(timeout=CONNECT_TIMEOUT)
        workflow_task = asyncio.create_task(workflow_app.aloop())

        # With two apps entered, the ambient rath/postman context is ambiguous,
        # so address every remote call explicitly to the workflow app.
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

        for task in (provider_task, workflow_task):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_workflow_calls_two_separate_apps(deployment: Deployment) -> None:
    """A workflow app calls two independent provider apps via declared deps.

    This is the full scenario: two genuinely separate apps (``atest`` exposing
    ``do_stuff`` and ``btest`` exposing ``do_another_stuff``) plus a third
    workflow app that declares a dependency on each and composes their results.
    """

    # --- Provider app A: atest -----------------------------------------------
    atest_app = build_fresh_rekuest(
        deployment, token="atest_token"
    )

    def do_stuff(printer: str) -> str:
        """Stitch a list of images."""
        return "stitched-" + printer

    atest_app.register(do_stuff)

    # --- Provider app B: btest -----------------------------------------------
    btest_app = build_fresh_rekuest(
        deployment, token="btest_token"
    )

    def do_another_stuff(ptiner: str) -> str:
        """Segment an image."""
        return "segmented-" + ptiner

    btest_app.register(do_another_stuff)

    # --- Workflow app: depends on both providers -----------------------------
    workflow_app = build_fresh_rekuest(
        deployment, token="workflow_token"
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
        # Connect the providers before the workflow that depends on them, awaiting
        # each acknowledgement so the ordering is deterministic. Once every agent
        # is acknowledged its implementations are live and the dependency resolves
        # with no extra settling.
        await atest_app.aconnect(timeout=CONNECT_TIMEOUT)
        atest_task = asyncio.create_task(atest_app.aloop())
        await btest_app.aconnect(timeout=CONNECT_TIMEOUT)
        btest_task = asyncio.create_task(btest_app.aloop())
        await workflow_app.aconnect(timeout=CONNECT_TIMEOUT)
        workflow_task = asyncio.create_task(workflow_app.aloop())

        # Address every remote call explicitly to the workflow app, since the
        # ambient rath/postman context is ambiguous with three apps entered.
        impl = await amy_implementation_at(
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
@pytest.mark.asyncio(loop_scope="session")
async def test_workflow_cancel_propagates_to_dependency(
    deployment: Deployment,
) -> None:
    """Cancelling a workflow must cancel the dependency tasks it spawned.

    This is the cancellation-propagation variant of the dual-app workflow tests.
    The provider exposes a long-running *threaded* (sync) action that loops,
    calling :func:`koil.check_cancelled` on every tick so it can cooperate with
    cancellation (a sync function runs in a worker thread, so it can only be
    interrupted at an explicit pause point). The workflow app declares a
    dependency on it and simply awaits it.

    We launch the workflow, wait until the provider's threaded loop is actually
    spinning, then cancel the workflow call. Cancelling the consuming ``acall``
    task makes the postman issue a backend ``cancel`` for the workflow
    task; the server fans that out to the workflow agent, which in turn
    cancels the dependency task it spawned on the provider. We then assert
    the provider's threaded task observed the cancellation (cancel propagated
    workflow -> dependency -> worker thread) instead of running to completion.
    """

    # All apps live in this single process, so the provider's threaded function
    # can record its lifecycle straight into these shared objects. ``started``
    # lets the test wait until the worker thread is actually running before it
    # tries to cancel; ``tracker`` records the terminal outcome.
    started = threading.Event()
    tracker: dict[str, int | bool] = {
        "cancelled": False,
        "completed": False,
        "iterations": 0,
    }

    # --- Provider app: a long-running threaded (sync) action -----------------
    provider = build_fresh_rekuest(
        deployment, token="atest_token"
    )

    def slow_stuff(printer: str) -> str:
        """Slowly stitch images, cooperating with cancellation.

        Sync functions run in a koil worker thread, which cannot be force-killed.
        Polling ``check_cancelled()`` each iteration lets koil raise
        ``ThreadCancelledError`` into the loop when the task is cancelled.
        """
        started.set()
        try:
            for i in range(600):  # up to ~60s; cancelled long before this
                check_cancelled()
                tracker["iterations"] = i
                time.sleep(0.1)
            tracker["completed"] = True
            return "stitched-" + printer
        except ThreadCancelledError:
            tracker["cancelled"] = True
            raise

    provider.register(slow_stuff)

    # --- Workflow app: declares a dependency on the provider and awaits it ----
    workflow_app = build_fresh_rekuest(
        deployment, token="workflow_token"
    )

    @declare(app="atest", auto_resolvable=True, min=1)
    class ATestLike(Protocol):
        async def slow_stuff(self, printer: str) -> str:
            """Slowly stitch images."""
            ...

    async def cancel_workflow(atest: ATestLike) -> str:
        """Call the long-running dependency and return its result."""
        return await atest.slow_stuff("printer")

    workflow_app.register(cancel_workflow)

    async with provider as provider, workflow_app as workflow_app:
        # Connect the provider before the workflow that depends on it, awaiting
        # each acknowledgement so the ordering is deterministic.
        await provider.aconnect(timeout=CONNECT_TIMEOUT)
        provider_task = asyncio.create_task(provider.aloop())
        await workflow_app.aconnect(timeout=CONNECT_TIMEOUT)
        workflow_task = asyncio.create_task(workflow_app.aloop())

        impl = await amy_implementation_at(
            "cancel_workflow",
            rath=workflow_app.rath,
        )

        # Launch the workflow but do NOT await it to completion: we want to
        # cancel it mid-flight.
        call_task = asyncio.create_task(
            acall(
                impl,
                postman=workflow_app.postman,
                structure_registry=workflow_app.structure_registry,
            )
        )

        # Wait until the provider's threaded loop is actually spinning, so we
        # know there is a live dependency task to cancel.
        for _ in range(150):
            if started.is_set() and tracker["iterations"] > 1:
                break
            await asyncio.sleep(0.1)
        assert started.is_set(), "Provider's threaded task never started"
        assert not call_task.done(), "Workflow finished before it could be cancelled"

        # Cancel the workflow call. This is the event under test: the cancel must
        # travel all the way down to the provider's worker thread.
        call_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await call_task

        # Give the cancellation time to propagate down the chain:
        # workflow task -> dependency task -> provider actor ->
        # threaded `check_cancelled()`.
        for _ in range(150):
            if tracker["cancelled"]:
                break
            await asyncio.sleep(0.1)

        assert tracker["cancelled"], (
            "Provider's threaded task was not cancelled - the workflow cancel "
            "did not propagate to its dependency task"
        )
        assert not tracker["completed"], (
            "Provider's threaded task ran to completion despite the cancellation"
        )

        for task in (provider_task, workflow_task):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_workflow_calls_two_separate_apps_async(deployment: Deployment) -> None:
    """A workflow app calls two independent provider apps via declared deps.

    This is the full scenario: two genuinely separate apps (``atest`` exposing
    ``do_stuff`` and ``btest`` exposing ``do_another_stuff``) plus a third
    workflow app that declares a dependency on each and composes their results.
    """

    # --- Provider app A: atest -----------------------------------------------
    atest_app = build_fresh_rekuest(
        deployment, token="atest_token"
    )

    def do_stuff(printer: str) -> str:
        """Stitch a list of images."""
        return "stitched-" + printer

    atest_app.register(do_stuff)

    # --- Provider app B: btest -----------------------------------------------
    btest_app = build_fresh_rekuest(
        deployment, token="btest_token"
    )

    def do_another_stuff(ptiner: str) -> str:
        """Segment an image."""
        return "segmented-" + ptiner

    btest_app.register(do_another_stuff)

    # --- Workflow app: depends on both providers -----------------------------
    workflow_app = build_fresh_rekuest(
        deployment, token="workflow_token"
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
        # Connect the providers before the workflow that depends on them, awaiting
        # each acknowledgement so the ordering is deterministic. Once every agent
        # is acknowledged its implementations are live and the dependency resolves
        # with no extra settling.
        await atest_app.aconnect(timeout=CONNECT_TIMEOUT)
        atest_task = asyncio.create_task(atest_app.aloop())
        await btest_app.aconnect(timeout=CONNECT_TIMEOUT)
        btest_task = asyncio.create_task(btest_app.aloop())
        await workflow_app.aconnect(timeout=CONNECT_TIMEOUT)
        workflow_task = asyncio.create_task(workflow_app.aloop())

        # Address every remote call explicitly to the workflow app, since the
        # ambient rath/postman context is ambiguous with three apps entered.
        impl = await amy_implementation_at(
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
