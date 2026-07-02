from collections.abc import Sequence

from rekuest_next.api.schema import (
    ActionDemandInput,
    ActionDependencyInput,
    DefinitionInput,
    StateDefinitionInput,
    StateDemandInput,
    StateDependencyInput,
)
from rekuest_next.definition.match import build_port_matches


def build_action_dependency_input(
    key: str,
    definition: DefinitionInput,
    *,
    app: str | None = None,
    action_key: str | None = None,
    version: str | None = None,
    hash: str | None = None,
    name: str | None = None,
    protocols: Sequence[str] | None = None,
    force_arg_length: int | None = None,
    force_return_length: int | None = None,
    match_ports: bool = True,
    allow_inactive: bool = True,
    optional: bool = False,
    description: str | None = None,
) -> ActionDependencyInput:
    """Build a named action requirement of an agent dependency.

    ``key`` is the local slot key that callers reference when assigning. The
    embedded :class:`ActionDemandInput` describes *which* concrete action must
    satisfy the slot.

    By default the demand is identified structurally (the port matches derived
    from ``definition`` plus its ``name``). Pass ``app`` and ``action_key`` to
    instead pin the slot to a specific action of a specific app — this is how a
    protocol method can point at another action instead of inheriting the
    protocol's core ``app`` + method key.
    """
    resolved_name = name
    if resolved_name is None and action_key is None and hash is None:
        # Only fall back to the local action name when the demand is not
        # already pinned by app/key or hash, so we don't over-constrain a
        # deliberate cross-action redirect.
        resolved_name = definition.name

    demand = ActionDemandInput(
        hash=hash,
        key=action_key,
        app=app,
        version=version,
        name=resolved_name,
        argMatches=build_port_matches(definition.args or ()) if match_ports else None,
        returnMatches=(
            build_port_matches(definition.returns or ()) if match_ports else None
        ),
        protocols=tuple(protocols) if protocols else None,
        forceArgLength=force_arg_length,
        forceReturnLength=force_return_length,
    )

    return ActionDependencyInput(
        key=key,
        description=description or definition.description,
        demand=demand,
        optional=optional,
        allowInactive=allow_inactive,
    )


def build_state_dependency_input(
    key: str,
    definition: StateDefinitionInput,
    *,
    state_key: str | None = None,
    app: str | None = None,
    hash: str | None = None,
    protocols: Sequence[str] | None = None,
    match_ports: bool = True,
    allow_inactive: bool = True,
    optional: bool = False,
    description: str | None = None,
) -> StateDependencyInput:
    """Build a named state requirement of an agent dependency.

    ``key`` is the local slot key callers reference when assigning; the embedded
    :class:`StateDemandInput` describes which agent state must satisfy the slot.
    Pass ``state_key`` (and optionally ``app``) to pin the slot to a specific
    state identity instead of matching it structurally.
    """
    demand = StateDemandInput(
        hash=hash,
        key=state_key,
        app=app,
        matches=build_port_matches(definition.ports or ()) if match_ports else None,
        protocols=tuple(protocols) if protocols else None,
    )

    return StateDependencyInput(
        key=key,
        description=description,
        demand=demand,
        optional=optional,
        allowInactive=allow_inactive,
    )
