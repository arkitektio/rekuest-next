"""Just a protocol for the serialization of ports."""

from typing import Any, Protocol, runtime_checkable

from rekuest_next.api.schema import PortKind


@runtime_checkable
class SerializablePort(Protocol):
    """Structural type for the ports the serialization layer walks over.

    The generated GraphQL port models (``ArgPort``, ``ReturnPort`` and their
    ``ChildPort``/``Nested`` variants) form a depth-limited hierarchy, where the
    deepest leaf nodes drop ``children``/``choices``/``default``. The
    serialization routines recurse over ``children`` uniformly, so this protocol
    captures the attributes they actually read. ``children``/``choices``/
    ``default`` are typed ``Any`` so the recursion type-checks regardless of the
    concrete nesting depth.
    """

    kind: PortKind
    key: str
    nullable: bool
    identifier: Any
    children: Any
    choices: Any
    default: Any
