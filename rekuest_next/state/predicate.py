"""Predicates to check if something is a state or a state class."""

from typing import TypeVar

from rekuest_next.definition.define import is_annotated, get_args
from rekuest_next.protocols import AnyState
from rekuest_next.state.types import ReadOnlyAnnotation

T = TypeVar("T")


def is_state(cls: type[T]) -> bool:
    """Check if a class is a state."""
    return hasattr(cls, "__rekuest_state__")


def is_app_context(cls: type[T]) -> bool:
    """Check if a class is an app context."""
    return hasattr(cls, "__rekuest_app_context__")


def is_read_only_state(cls: type[T]) -> bool:
    """Check if an annotation is a state marked read-only, i.e. ``ReadOnly[SomeState]``.

    The marker is a :class:`~rekuest_next.state.types.ReadOnlyAnnotation` *instance*
    carried in the ``Annotated`` extras, so it has to be matched with ``isinstance``.
    Comparing it against the ``ReadOnly`` type alias itself never matches, which silently
    classified such a parameter as neither writeable nor read-only — so it was dropped
    from the actor's kwargs entirely and the call failed with a missing argument.
    """
    if not is_annotated(cls):
        return False
    real_type, *annotations = get_args(cls)
    if not is_state(real_type):
        return False
    return any(isinstance(a, ReadOnlyAnnotation) for a in annotations)


def get_read_only_state_type(cls: type[T]) -> type[AnyState]:
    """Unwrap ``ReadOnly[SomeState]`` to ``SomeState``."""
    real_type, *_ = get_args(cls)
    return real_type


def get_state_name(cls: type[T]) -> str:
    """Get the name of a state class."""
    x = getattr(cls, "__rekuest_state__", None)
    if x is None:
        raise ValueError(f"Class {cls} is not a state")
    return x


def get_state_locks(cls: type[AnyState]) -> list[str]:
    """Get the locks required for a state class."""
    x = cls.__rekuest_state_config__.required_locks
    return x
