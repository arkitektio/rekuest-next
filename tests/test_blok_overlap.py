import pytest
from pydantic import ValidationError

from rekuest_next.api.schema import (
    AgentDependencyInput,
    ArgPortInput,
    BlokImplementationInput,
    CreateBlokInput,
    ImplementationInput,
    PortKind,
    ReturnPortInput,
    StateDependencyInput,
    StateImplementationInput,
)
from rekuest_next.blok.registry import (
    _create_action_dependency,
    _create_state_dependency,
)
from rekuest_next.declare import DeclaredAgentAction, DeclaredAgentState
from rekuest_next.definition.define import prepare_definition
from rekuest_next.definition.match import build_port_match, build_port_matches
from rekuest_next.definition.registry import DefinitionRegistry
from rekuest_next.state.registry import StateRegistry


def test_build_port_match_preserves_nested_shape() -> None:
    port = ArgPortInput(
        key="items",
        kind=PortKind.LIST,
        nullable=False,
        children=(
            ArgPortInput(
                key="...",
                kind=PortKind.STRING,
                nullable=False,
            ),
        ),
    )

    match = build_port_match(2, port)

    assert match.at == 2
    assert match.key == "items"
    assert match.children is not None
    assert len(match.children) == 1
    assert match.children[0].at == 0
    assert match.children[0].key == "..."
    assert match.children[0].kind == PortKind.STRING


def test_build_port_matches_returns_none_for_empty_ports() -> None:
    assert build_port_matches(()) is None


def test_declared_action_and_blok_registry_build_same_action_dependency(
    simple_registry,
) -> None:
    class DemoProtocol:
        def run(self, value: str) -> str:
            return value

    declared = DeclaredAgentAction(DemoProtocol.run, "demo", "run")

    definition_registry = DefinitionRegistry()
    definition_registry.register_at_interface(
        "run",
        ImplementationInput(
            definition=prepare_definition(
                DemoProtocol.run,
                structure_registry=simple_registry,
                omitfirst=1,
            ),
            dependencies=(),
            dynamic=False,
            interface="run",
        ),
        lambda *args, **kwargs: None,
    )

    declared_dependency = declared.to_dependency_input("run")
    blok_dependency = _create_action_dependency("run", definition_registry)

    assert declared_dependency.model_dump() == blok_dependency.model_dump()


def test_declared_state_and_blok_registry_build_same_state_dependency(
    simple_registry,
) -> None:
    class DemoState:
        value: str

    declared = DeclaredAgentState(DemoState, "demo", "status")

    state_registry = StateRegistry()
    state_registry.register(
        DemoState,
        StateImplementationInput(
            interface="status",
            definition=declared.definition,
        ),
        simple_registry,
    )

    declared_dependency = declared.to_dependency_input("status")
    blok_dependency = _create_state_dependency("status", state_registry)

    assert declared_dependency.model_dump() == blok_dependency.model_dump()


@pytest.mark.parametrize(
    ("model_cls", "base_kwargs"),
    [
        (CreateBlokInput, {"name": "demo"}),
        (
            BlokImplementationInput,
            {
                "key": "demo",
                "components": (),
            },
        ),
    ],
)
def test_blok_models_reject_missing_demo_state_keys(model_cls, base_kwargs) -> None:
    dependency = AgentDependencyInput(
        key="service",
        optional=False,
        auto_resolvable=False,
        state_demands=(
            StateDependencyInput(
                key="status",
                optional=False,
            ),
        ),
    )

    with pytest.raises(ValidationError, match="missing key 'status'"):
        model_cls(
            **base_kwargs,
            dependencies=(dependency,),
            demo_state={"service": {}},
        )


@pytest.mark.parametrize(
    ("model_cls", "base_kwargs"),
    [
        (CreateBlokInput, {"name": "demo"}),
        (
            BlokImplementationInput,
            {
                "key": "demo",
                "components": (),
            },
        ),
    ],
)
def test_blok_models_reject_extra_demo_state_keys(model_cls, base_kwargs) -> None:
    dependency = AgentDependencyInput(
        key="service",
        optional=False,
        auto_resolvable=False,
        state_demands=(
            StateDependencyInput(
                key="status",
                optional=False,
            ),
        ),
    )

    with pytest.raises(ValidationError, match="extra keys not referenced in blok"):
        model_cls(
            **base_kwargs,
            dependencies=(dependency,),
            demo_state={"service": {"status": "ready", "other": "nope"}},
        )


@pytest.mark.parametrize(
    ("model_cls", "base_kwargs"),
    [
        (CreateBlokInput, {"name": "demo"}),
        (
            BlokImplementationInput,
            {
                "key": "demo",
                "components": (),
            },
        ),
    ],
)
def test_blok_models_accept_matching_demo_state(model_cls, base_kwargs) -> None:
    dependency = AgentDependencyInput(
        key="service",
        optional=False,
        auto_resolvable=False,
        state_demands=(
            StateDependencyInput(
                key="status",
                optional=False,
                port_matches=build_port_matches(
                    (
                        ReturnPortInput(
                            key="value",
                            kind=PortKind.STRING,
                            nullable=False,
                        ),
                    )
                ),
            ),
        ),
    )

    model = model_cls(
        **base_kwargs,
        dependencies=(dependency,),
        demo_state={"service": {"status": {"value": "ready"}}},
    )

    assert model.demo_state == {"service": {"status": {"value": "ready"}}}
