"""Utils for Rekuest Next"""

from typing import Any


def is_local_var(type_: Any) -> bool:  # noqa: ANN401
    """Check if the type is a local variable (context or state)."""

    from rekuest_next.state.predicate import is_state
    from rekuest_next.agents.context import is_context

    return is_context(type_) or is_state(type_)
