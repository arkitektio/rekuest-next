"""Utils for Rekuest Next"""

from typing import Any


def is_local_var(type_: Any) -> bool:  # noqa: ANN401
    """Check if the type is a local variable (context or state).

    Local variables are injected by the agent, so they must not become ports on the
    definition. ``ReadOnly[SomeState]`` counts too: it is an ``Annotated`` wrapper, so
    ``is_state`` does not see through it, and without this a read-only state parameter
    was published as a required argument the caller could never supply.
    """

    from rekuest_next.state.predicate import is_read_only_state, is_state
    from rekuest_next.agents.context import is_context

    return is_context(type_) or is_state(type_) or is_read_only_state(type_)
