"""Per-call context threaded through the kind-dispatch tables."""

from dataclasses import dataclass, replace
from typing import Any, Awaitable, Callable, Dict, Optional, Sequence, Tuple

from rekuest_next.actors.types import Shelver
from rekuest_next.api.schema import PortKind
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.structures.serialization.protocols import SerializablePort


@dataclass(frozen=True)
class SerializationContext:
    """What a (de)serialization step needs besides the port and the value.

    ``path``/``depth`` only feed error messages; ``shelver`` is only present on
    the actor side, where memory structures are resolved against the local
    shelve.
    """

    registry: StructureRegistry
    shelver: Optional[Shelver] = None
    path: Tuple[str, ...] = ()
    depth: int = 0

    @classmethod
    def build(
        cls,
        registry: StructureRegistry,
        shelver: Optional[Shelver] = None,
        path: Sequence[str] | None = None,
        depth: int = 0,
    ) -> "SerializationContext":
        return cls(
            registry=registry, shelver=shelver, path=tuple(path or ()), depth=depth
        )

    def child(self, *parts: str) -> "SerializationContext":
        """Context for a nested port one level down."""
        return replace(self, path=(*self.path, *parts), depth=self.depth + 1)

    def require_shelver(self) -> Shelver:
        if self.shelver is None:
            raise RuntimeError(
                "This serialization step needs a shelver but none was provided"
            )
        return self.shelver


Handler = Callable[[SerializablePort, Any, SerializationContext], Awaitable[Any]]
KindTable = Dict[PortKind, Handler]


def single_child(port: SerializablePort) -> SerializablePort | None:
    """The only child of a LIST/DICT port, or ``None`` if the port is malformed."""
    if not port.children or len(port.children) != 1:
        return None
    return port.children[0]


def union_index(value: Any) -> Tuple[int | None, str | None]:  # noqa: ANN401
    """Parse a tagged ``{"__use": i, "__value": ...}`` union value.

    Returns ``(index, None)`` on success, ``(None, reason)`` otherwise.
    """
    if not isinstance(value, dict) or "__use" not in value or "__value" not in value:
        return None, (
            "Union value needs to be a tagged "
            '{"__use": index, "__value": ...} dict, got '
            f"{type(value).__name__}"
        )
    index = value["__use"]
    if not isinstance(index, int) or isinstance(index, bool):
        return (
            None,
            f"Union '__use' must be an integer index, got {type(index).__name__}",
        )
    return index, None
