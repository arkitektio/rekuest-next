"""Predicates to check if something is a state or a state class."""

from typing import Type, TypeVar

from rekuest_next.definition.define import is_annotated, get_args
from rekuest_next.state.types import ReadOnly

T = TypeVar("T")


def is_state(cls: Type[T]) -> bool:
    """Check if a class is a state."""
    return hasattr(cls, "__rekuest_state__")


def is_read_only_state(cls: Type[T]) -> bool:
    """Check if a class is a read-only state."""
    if is_annotated(cls):
        real_type, *annotations = get_args(cls)
        if is_state(real_type):
            for annotation in annotations:
                if annotation is ReadOnly:
                    return True
                return False

            return True
        else:
            return False
    return False


def get_state_name(cls: Type[T]) -> str:
    """Get the name of a state class."""
    x = getattr(cls, "__rekuest_state__", None)
    if x is None:
        raise ValueError(f"Class {cls} is not a state")
    return x


def get_state_locks(cls: Type[T]) -> list[str]:
    """Get the locks required for a state class."""
    x = getattr(cls, "__rekuest_state_locks__", [])
    return x
