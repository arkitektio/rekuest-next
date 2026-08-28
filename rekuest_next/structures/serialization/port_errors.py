"""Error helpers that attach port / path context to (de)serialization failures."""

from typing import Any, Sequence

from rekuest_next.structures.errors import ExpandingError, ShrinkingError
from rekuest_next.structures.serialization.protocols import SerializablePort


def _short_repr(value: Any, limit: int = 200) -> str:  # noqa: ANN401
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _format_path_tree(path: Sequence[str] | None) -> str:
    if not path:
        return "- <root>"
    lines = []
    for depth, part in enumerate(path):
        indent = "  " * depth
        lines.append(f"{indent}- {part}")
    return "\n".join(lines)


def to_shrink_port_error(
    port: SerializablePort,
    value: Any,
    message: str,
    *,
    path: Sequence[str] | None = None,
    depth: int | None = None,
) -> ShrinkingError:
    """Helper function to create a ShrinkingError with port context."""
    depth_info = f"Depth: {depth}" if depth is not None else "Depth: unknown"
    tree_info = _format_path_tree(path)
    return ShrinkingError(
        "Error shrinking value with nested path:\n"
        f"{tree_info}\n"
        f"Port: {port.key} ({port.kind})\n"
        f"Value: {_short_repr(value)}\n"
        f"{depth_info}\n"
        f"Reason: {message}"
    )


def to_port_error(
    port: SerializablePort,
    value: Any,
    message: str,
    *,
    path: Sequence[str] | None = None,
    depth: int | None = None,
) -> ExpandingError:
    """Helper function to create an ExpandingError with port context."""
    depth_info = f"Depth: {depth}" if depth is not None else "Depth: unknown"
    tree_info = _format_path_tree(path)
    return ExpandingError(
        "Error expanding value with nested path:\n"
        f"{tree_info}\n"
        f"Port: {port.key} ({port.kind})\n"
        f"Value: {_short_repr(value)}\n"
        f"{depth_info}\n"
        f"Reason: {message}"
    )
