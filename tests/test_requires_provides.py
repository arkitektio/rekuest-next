"""Integration tests for ``Requires`` / ``Provides`` port annotations.

A function can annotate its inputs with :class:`~rekuest_next.annotations.Requires`
descriptors (constraints the bound value must satisfy, e.g. a filename matching
``.*\\.tiff?``) and its outputs with :class:`~rekuest_next.annotations.Provides`
descriptors (guarantees about the produced value, e.g. an ``x`` dimension ``>= 1``).

These descriptors are part of the action *definition*: they ride along on the
``ArgPort`` (``requires``) and ``ReturnPort`` (``provides``) of the implementation
the agent registers with the server. This test stands up a real app against the
shared docker deployment, registers such a function, and then reads the stored
implementation back off the server to assert the descriptors survived the
round-trip exactly as declared -- i.e. the server *respects* them.

The generated typed client (``amy_implementation_at``) does not select the
``requires`` / ``provides`` fields, so we issue a raw GraphQL query that does.
"""

import asyncio
from typing import Annotated

import pytest
from dokker import Deployment

from rekuest_next.annotations import Provides, Requires
from rekuest_next.api.schema import (
    ProvidesOperator,
    RequiresOperator,
    amy_implementation_at,
)
from rekuest_next.remote import acall

from .conftest import build_fresh_rekuest

# Input must be a TIFF filename -- a MATCHES constraint on the bound value.
TiffFileName = Annotated[
    str,
    Requires(key="filename", operator=RequiresOperator.MATCHES, value=r".*\.tiff?"),
]

# Output guarantees an 'x' dimension >= 1 (a multi-dimensional line).
LargLine = Annotated[
    int,
    Provides(key="x", operator=ProvidesOperator.GTE, value=1),
]


def capture_image(file: TiffFileName) -> LargLine:
    """Pretend to capture an image from a TIFF file and return its 'x' extent.

    The input must be a ``.tif``/``.tiff`` filename and the output is guaranteed
    to have an ``x`` dimension greater than or equal to 1.
    """
    return len(file)


# A raw query that DOES select requires/provides, which the generated
# `MyImplementationAt` fragments omit.
IMPLEMENTATION_WITH_DESCRIPTORS = """
query ImplWithDescriptors($interface: String) {
  myImplementationAt(interface: $interface) {
    id
    interface
    action {
      name
      args {
        key
        kind
        requires { key operator value }
      }
      returns {
        key
        kind
        provides { key operator value }
      }
    }
  }
}
"""


@pytest.mark.integration
@pytest.mark.asyncio(scope="session")
async def test_server_respects_requires_and_provides(deployment: Deployment) -> None:
    """Register a function carrying Requires/Provides and read them back.

    Asserts the server stored and exposes the descriptors exactly as declared on
    both the arg port (requires) and the return port (provides).
    """
    app = build_fresh_rekuest(deployment, token="standalone_token")
    app.register(capture_image)

    async with app as app:
        task = asyncio.create_task(app.arun())
        await asyncio.sleep(5)  # Wait for the agent to register with the server.

        try:
            result = await app.rath.aquery(
                IMPLEMENTATION_WITH_DESCRIPTORS,
                {"interface": "capture_image"},
            )

            action = result.data["myImplementationAt"]["action"]

            # --- Requires round-tripped onto the (single) arg port ----------
            (arg,) = action["args"]
            assert arg["key"] == "file"
            assert arg["requires"] == [
                {"key": "filename", "operator": "MATCHES", "value": r".*\.tiff?"}
            ]

            # --- Provides round-tripped onto the (single) return port -------
            (ret,) = action["returns"]
            assert ret["provides"] == [{"key": "x", "operator": "GTE", "value": 1}]

            # And the function still runs end-to-end with a conforming input.
            impl = await amy_implementation_at("capture_image", rath=app.rath)
            answer = await acall(
                impl,
                postman=app.postman,
                structure_registry=app.structure_registry,
                file="scan.tiff",
            )
            assert answer == len("scan.tiff")
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
