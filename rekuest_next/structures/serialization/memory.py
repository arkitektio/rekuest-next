"""Wire format for memory-structure references.

A memory structure never leaves the agent that created it. What travels is a
reference to its *drawer* on that agent's shelve, always as
``{"__identifier": <port identifier>, "object": <drawer id>}`` — the same
envelope structures use. Client-side, the reference is exposed as the bare
drawer id string, which is also what callers hand back in to pipe it into the
next call.
"""

from typing import Any

from rekuest_next.structures.errors import ExpandingError, ShrinkingError
from rekuest_next.structures.serialization.protocols import SerializablePort


def shrink_memory_reference(
    port: SerializablePort,
    value: Any,  # noqa: ANN401
) -> dict[str, Any]:
    """Wrap a drawer id (or an already-wrapped reference) into the envelope."""
    if isinstance(value, dict) and "object" in value:
        value = value["object"]
    if not isinstance(value, (str, int)):
        raise ShrinkingError(
            "Memory structures are passed as a reference to a memory drawer "
            f"(str), but got {type(value).__name__}"
        )
    return {"__identifier": port.identifier, "object": str(value)}


def expand_memory_reference(
    port: SerializablePort,
    value: Any,  # noqa: ANN401
) -> str:
    """Unwrap the envelope to the drawer id; a bare id is accepted as-is."""
    if isinstance(value, (str, int)):
        return str(value)
    if not isinstance(value, dict):
        raise ExpandingError(
            f"Expected a memory reference dict or drawer id, got {type(value).__name__}"
        )
    if "object" not in value:
        raise ExpandingError(f"Memory reference is missing its `object` key: {value}")
    if "__identifier" in value and value["__identifier"] != port.identifier:
        raise ExpandingError(
            f"Memory reference identifier mismatch: expected {port.identifier}, "
            f"got {value['__identifier']}"
        )
    return str(value["object"])
