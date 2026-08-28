"""Integration tests for piping a *memory structure* between calls.

Each test stands up its **own** ``RekuestNext`` with a **fresh** ``AppRegistry``
(via :func:`build_fresh_rekuest`) against the shared, already-running deployment,
registers its functions, runs the agent, and drives real calls with ``acall`` --
exactly like ``test_app_run`` does, just with a per-test app instead of a shared
one.

A **memory structure** is any object the structure registry cannot serialise
(here, plain classes with no ``ashrink``/``aexpand``). Instead of being
serialised onto the wire, it is parked on the agent's shelve and only an opaque
reference (a *memory drawer* id, wrapped as ``{"__identifier", "object"}`` on
the wire and exposed client-side as the bare id) travels between server and
client. Piping that
reference from one call's output into the next call's input therefore makes the
second call resolve the *same* live object the first call produced -- which is
the whole point of these tests.
"""

import asyncio

import pytest
from dokker import Deployment

from rekuest_next.api.schema import amy_implementation_at
from rekuest_next.remote import acall

from .conftest import CONNECT_TIMEOUT, build_fresh_rekuest


class Image:
    """A pretend in-memory image -- not serialisable, lives on the shelve."""

    def __init__(self, pixels: list[int]) -> None:
        self.pixels = pixels


class Mask:
    """A pretend in-memory mask derived from an :class:`Image`."""

    def __init__(self, source: Image, threshold: int) -> None:
        self.source = source
        self.threshold = threshold
        self.area = sum(1 for pixel in source.pixels if pixel >= threshold)


def _drawer(reference: object) -> str:
    """A piped memory-structure reference arrives client-side as the bare
    memory-drawer id string, ready to be handed to the next call as-is."""
    assert isinstance(reference, str), (
        f"Expected a memory drawer id string, got {reference!r}"
    )
    return reference


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_pipe_memory_structure_between_calls(deployment: Deployment) -> None:
    """Output of one call is piped into another, resolving the live instance."""

    app = build_fresh_rekuest(deployment, token="standalone_token")

    def make_image(size: int) -> Image:
        """Create an in-memory image."""
        return Image(pixels=list(range(size)))

    def count_pixels(image: Image) -> int:
        """Count the pixels of an image received from a previous call."""
        return len(image.pixels)

    app.register(make_image)
    app.register(count_pixels)

    async with app as app:
        await app.aconnect(timeout=CONNECT_TIMEOUT)
        task = asyncio.create_task(app.aloop())

        make_impl = await amy_implementation_at("make_image")
        reference = await acall(make_impl, size=5)

        count_impl = await amy_implementation_at("count_pixels")
        result = await acall(count_impl, image=_drawer(reference))

        assert result == 5, f"Expected the piped image to have 5 pixels, got {result}"

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_three_stage_memory_pipeline(deployment: Deployment) -> None:
    """Chain three calls, threading memory structures all the way through."""

    app = build_fresh_rekuest(deployment, token="standalone_token")

    def make_image(size: int) -> Image:
        """Create an in-memory image."""
        return Image(pixels=list(range(size)))

    def threshold_image(image: Image, at: int) -> Mask:
        """Derive an in-memory mask from an image."""
        return Mask(source=image, threshold=at)

    def measure_mask(mask: Mask) -> int:
        """Measure the area of a mask received from a previous call."""
        return mask.area

    app.register(make_image)
    app.register(threshold_image)
    app.register(measure_mask)

    async with app as app:
        await app.aconnect(timeout=CONNECT_TIMEOUT)
        task = asyncio.create_task(app.aloop())

        make_impl = await amy_implementation_at("make_image")
        image_ref = await acall(make_impl, size=10)

        threshold_impl = await amy_implementation_at("threshold_image")
        mask_ref = await acall(threshold_impl, image=_drawer(image_ref), at=4)

        measure_impl = await amy_implementation_at("measure_mask")
        area = await acall(measure_impl, mask=_drawer(mask_ref))

        # pixels 4..9 are >= 4 -> area 6, computed on the real piped objects.
        assert area == 6, f"Expected mask area 6, got {area}"

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_each_test_gets_a_fresh_app_registry(deployment: Deployment) -> None:
    """A freshly built app starts with an empty registry, isolated from others.

    Other tests in this module register ``make_image``/``count_pixels`` etc. on
    their own apps; this one must not see any of them -- proving the per-test
    ``AppRegistry`` isolation that ``build_fresh_rekuest`` provides.
    """

    app = build_fresh_rekuest(deployment, token="standalone_token")

    assert app.agent.app_registry.implementations == {}

    def only_here(x: int) -> int:
        """A function registered solely on this test's app."""
        return x

    app.register(only_here)

    assert set(app.agent.app_registry.implementations) == {"only_here"}


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_memory_structure_round_trips_through_dependency(
    deployment: Deployment,
) -> None:
    """A workflow pipes a memory structure between two dependency calls.

    The provider creates an ``Image`` (parked on *its* shelve) and hands back a
    reference; the workflow feeds that reference straight into the provider's
    second method via the declared dependency proxy. Both hops go through the
    actor-side serialisation path (``acall_dependency``), which must speak the
    same ``{"__identifier", "object"}`` envelope as the client path.
    """
    from typing import Protocol

    from rekuest_next.declare import declare

    provider = build_fresh_rekuest(deployment, token="atest_token")

    def make_image(size: int) -> Image:
        """Create an in-memory image."""
        return Image(pixels=list(range(size)))

    def count_pixels(image: Image) -> int:
        """Count the pixels of an image received from a previous call."""
        return len(image.pixels)

    provider.register(make_image)
    provider.register(count_pixels)

    workflow_app = build_fresh_rekuest(deployment, token="workflow_token")

    @declare(app="atest", auto_resolvable=True, min=1)
    class ImageProvider(Protocol):
        def make_image(self, size: int) -> Image:
            """Create an in-memory image."""
            ...

        def count_pixels(self, image: Image) -> int:
            """Count the pixels of an image received from a previous call."""
            ...

    def pipe_through_dependency(atest: ImageProvider, size: int) -> int:
        """Create an image on the provider and count its pixels there."""
        reference = atest.make_image(size)
        assert isinstance(reference, str), (
            f"Expected a drawer id from the dependency, got {reference!r}"
        )
        return atest.count_pixels(reference)

    workflow_app.register(pipe_through_dependency)

    async with provider as provider, workflow_app as workflow_app:
        await provider.aconnect(timeout=CONNECT_TIMEOUT)
        provider_task = asyncio.create_task(provider.aloop())
        await workflow_app.aconnect(timeout=CONNECT_TIMEOUT)
        workflow_task = asyncio.create_task(workflow_app.aloop())

        impl = await amy_implementation_at(
            "pipe_through_dependency", rath=workflow_app.rath
        )
        result = await acall(
            impl,
            size=7,
            postman=workflow_app.postman,
            structure_registry=workflow_app.structure_registry,
        )
        assert result == 7, (
            f"Expected 7 pixels counted via the dependency, got {result}"
        )

        for task in (provider_task, workflow_task):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
