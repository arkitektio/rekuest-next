"""Type-level definitions shared by the agent package.

Protocol-like markers, type variables and the decorators that stamp them. Data
containers live in :mod:`rekuest_next.agents.dataclasses`; behaviour lives on
:class:`rekuest_next.agents.base.BaseAgent`.
"""

from typing import TypeVar


class AppContext:
    """Protocol for the app context that is passed to the hooks."""

    __rekuest_app_context__: str


T = TypeVar("T")


def app_context(
    cls: type[T],
) -> type[T]:
    """Decorator to register a class as an app context."""

    setattr(cls, "__rekuest_app_context__", cls.__name__)
    return cls


__all__ = ["AppContext", "T", "app_context"]
