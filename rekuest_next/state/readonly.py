"""Read-only views over agent state.

An actor can declare a state it only reads. That declaration used to be advisory: the
agent handed back the very same live object it gives a writer, so an actor could write to
a state it declared read-only and the write would publish a patch like any other. These
views make the declaration real.

A view is a *subclass of the state's own class sharing its instance dict*, which matters
for three reasons: ``isinstance(view, MyState)`` still holds, so user functions annotated
with the state type keep working; reads see live values rather than a snapshot; and
writes hit an overridden ``__setattr__`` that raises. Nested lists and dicts are wrapped
on the way out, so ``state.items.append(...)`` is blocked too.

Known limit: a *method defined on the state class* that mutates ``self`` writes through to
the underlying object. Blocking that would mean intercepting arbitrary user code; the
declaration covers attribute and container mutation, which is what publishes patches.
"""

import dataclasses
from collections.abc import Mapping, Sequence
from typing import Any, TypeVar
from collections.abc import Iterator

__all__ = ["ReadOnlyStateError", "read_only_view"]

T = TypeVar("T")


class ReadOnlyStateError(RuntimeError):
    """Raised when an actor writes to a state it declared read-only."""


def _refuse(state_name: str, detail: str) -> "ReadOnlyStateError":
    return ReadOnlyStateError(
        f"Cannot modify '{state_name}': this actor declared it read-only. {detail} "
        f"Declare the state as writeable if the actor needs to change it."
    )


class _ReadOnlyContainer:
    """Shared machinery for live, non-mutating container views.

    Subclasses set ``_mutators`` (method names that would mutate the target) and
    ``_kind_name`` (used in error messages) and add the ABC they present as.
    """

    __slots__ = ("_target", "_state_name")

    _mutators: frozenset[str] = frozenset()
    _kind_name: str = "container"

    def __init__(self, target: Any, state_name: str) -> None:  # noqa: ANN401
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_state_name", state_name)

    def __getitem__(self, key: Any) -> Any:  # noqa: ANN401
        """Read one item, wrapping nested containers too."""
        return _wrap(self._target[key], self._state_name)

    def __len__(self) -> int:
        """Size of the underlying container."""
        return len(self._target)

    def __repr__(self) -> str:
        """Show the underlying container."""
        return f"ReadOnly({self._target!r})"

    def __setitem__(self, key: Any, value: Any) -> None:  # noqa: ANN401
        """Refuse: this container belongs to a read-only state."""
        raise _refuse(self._state_name, f"It holds a read-only {self._kind_name}.")

    def __delitem__(self, key: Any) -> None:  # noqa: ANN401
        """Refuse: this container belongs to a read-only state."""
        raise _refuse(self._state_name, f"It holds a read-only {self._kind_name}.")

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401
        """Forward reads; refuse the mutators."""
        if name in type(self)._mutators:
            raise _refuse(
                self._state_name,
                f"'{name}' would modify a read-only {self._kind_name}.",
            )
        return getattr(object.__getattribute__(self, "_target"), name)


class _ReadOnlySequence(_ReadOnlyContainer, Sequence[Any]):
    """A live, non-mutating view of a list held in read-only state."""

    __slots__ = ()

    _mutators = frozenset(
        {"append", "extend", "insert", "remove", "pop", "clear", "sort", "reverse"}
    )
    _kind_name = "list"

    def __iter__(self) -> Iterator[Any]:
        """Iterate, wrapping nested containers."""
        return (_wrap(item, self._state_name) for item in self._target)

    def __eq__(self, other: object) -> bool:
        """Compare against the underlying list."""
        return list(self._target) == list(other) if isinstance(other, (list, Sequence)) else NotImplemented


class _ReadOnlyMapping(_ReadOnlyContainer, Mapping[Any, Any]):
    """A live, non-mutating view of a dict held in read-only state."""

    __slots__ = ()

    _mutators = frozenset({"update", "setdefault", "pop", "popitem", "clear"})
    _kind_name = "dict"

    def __iter__(self) -> Iterator[Any]:
        """Iterate the underlying keys."""
        return iter(self._target)

    def __eq__(self, other: object) -> bool:
        """Compare against the underlying dict."""
        return dict(self._target) == dict(other) if isinstance(other, (dict, Mapping)) else NotImplemented


def _wrap(value: Any, state_name: str) -> Any:  # noqa: ANN401
    """Wrap containers so nested mutation is refused too; pass anything else through."""
    if isinstance(value, (str, bytes)):
        return value
    if isinstance(value, dict):
        return _ReadOnlyMapping(value, state_name)
    if isinstance(value, list):
        return _ReadOnlySequence(value, state_name)
    return value


#: One read-only class per (state class, state name), so repeated lookups do not
#: rebuild the type. The view shares the state's instance dict, so the name cannot
#: live on the instance; keying the cache on it keeps error messages accurate when
#: several states share one dataclass.
_view_classes: dict[tuple[type, str], type] = {}


def _read_only_class(cls: type, state_name: str) -> type:
    """Build (and cache) the read-only subclass for one state class and name."""
    cached = _view_classes.get((cls, state_name))
    if cached is not None:
        return cached

    def __setattr__(self: Any, name: str, value: Any) -> None:  # noqa: ANN401, N807
        raise _refuse(state_name, f"Assigning '{name}' would modify it.")

    def __delattr__(self: Any, name: str) -> None:  # noqa: ANN401, N807
        raise _refuse(state_name, f"Deleting '{name}' would modify it.")

    def __getattribute__(self: Any, name: str) -> Any:  # noqa: ANN401, N807
        value = object.__getattribute__(self, name)
        return _wrap(value, state_name) if not name.startswith("_") else value

    def __eq__(self: Any, other: object) -> bool:  # noqa: N807
        # The dataclass __eq__ requires an exact class match, which a view never is.
        if not isinstance(other, cls):
            return NotImplemented
        return all(
            object.__getattribute__(self, f.name) == getattr(other, f.name)
            for f in dataclasses.fields(cls)  # type: ignore[arg-type]
        )

    def __repr__(self: Any) -> str:  # noqa: N807
        return f"ReadOnly({cls.__name__})"

    view_cls = type(
        f"ReadOnly{cls.__name__}",
        (cls,),
        {
            "__setattr__": __setattr__,
            "__delattr__": __delattr__,
            "__getattribute__": __getattribute__,
            "__eq__": __eq__,
            "__repr__": __repr__,
            "__hash__": None,
            "__doc__": f"A read-only view of {cls.__name__}.",
        },
    )
    _view_classes[(cls, state_name)] = view_cls
    return view_cls


def read_only_view(state: T, state_name: str) -> T:
    """Return a live, non-writeable view of ``state``.

    Falls back to the state itself if it has no instance dict to share (a
    ``slots=True`` dataclass), since a view over it could not stay live. That is the old
    behaviour, and is logged by the caller rather than failing the assignment.
    """
    cls: type[Any] = type(state)
    if not hasattr(state, "__dict__"):
        return state

    view_cls = _read_only_class(cls, state_name)
    view = object.__new__(view_cls)
    # Share the instance dict rather than copy it, so the view tracks live writes made
    # through the writeable handle.
    object.__setattr__(view, "__dict__", state.__dict__)
    return view  # type: ignore[return-value]
