"""Predicates to check if something is a state or a state class."""

from typing import Type, TypeVar

T = TypeVar("T")


def is_state(cls: Type[T]) -> bool:
    """Check if a class is a state."""
    return hasattr(cls, "__rekuest_state__")


def get_state_name(cls: Type[T]) -> str:
    """Get the name of a state class."""
    x = getattr(cls, "__rekuest_state__", None)
    if x is None:
        raise ValueError(f"Class {cls} is not a state")
    return x
