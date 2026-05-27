from rekuest_next.api.schema import (
    ActionDependencyInput,
    DefinitionInput,
    StateDefinitionInput,
    StateDependencyInput,
)
from rekuest_next.definition.match import build_port_matches


def build_action_dependency_input(
    key: str,
    definition: DefinitionInput,
    allow_inactive: bool = True,
    optional: bool = False,
) -> ActionDependencyInput:
    return ActionDependencyInput(
        key=key,
        name=definition.name,
        description=definition.description,
        arg_matches=build_port_matches(definition.args),
        return_matches=build_port_matches(definition.returns),
        optional=optional,
        allow_inactive=allow_inactive,
    )


def build_state_dependency_input(
    key: str,
    state_key: str,
    definition: StateDefinitionInput,
    allow_inactive: bool = True,
    optional: bool = False,
    description: str | None = None,
) -> StateDependencyInput:
    return StateDependencyInput(
        key=key,
        state_key=state_key,
        name=definition.name,
        description=description,
        port_matches=build_port_matches(definition.ports),
        optional=optional,
        allow_inactive=allow_inactive,
    )
