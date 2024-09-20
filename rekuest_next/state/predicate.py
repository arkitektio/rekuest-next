from typing import Type, TypeVar

T = TypeVar("T")


def is_state(cls: Type[T]) -> bool:
    return hasattr(cls, "__rekuest_state__")


def get_state_name(cls: Type[T]) -> str:
    x = getattr(cls, "__rekuest_state__", None)
    if x is None:
        raise ValueError(f"Class {cls} is not a state")
    return x
