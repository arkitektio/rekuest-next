"""Tests that a ``withStateChoices`` widget validates against the available dependencies.

When a function registers a state choice widget, the widget encodes a ``dependency``
key. The corresponding dependency has to be available in the
``ImplementationInput.dependencies`` or the implementation is rejected. A ``self.``
reference (``dependency=None``) points at the function's own state and is always allowed.
"""

import pytest
from pydantic import ValidationError

from rekuest_next.api.schema import (
    AgentDependencyInput,
    ImplementationInput,
    PortKind,
    ReturnPortInput,
    StateDemandInput,
    StateDependencyInput,
)
from rekuest_next.declare import declare, declare_state
from rekuest_next.definition.define import prepare_definition
from rekuest_next.definition.match import build_port_matches
from rekuest_next.app import AppRegistry
from rekuest_next.register import register_func, RegisterConfig
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.widgets import withStateChoices


def _camera_dependency() -> AgentDependencyInput:
    return AgentDependencyInput(
        key="camera",
        optional=False,
        auto_resolvable=False,
        state_dependencies=(
            StateDependencyInput(
                key="state",
                optional=False,
                demand=StateDemandInput(
                    matches=build_port_matches(
                        (
                            ReturnPortInput(
                                key="exposure_ms",
                                kind=PortKind.FLOAT,
                                nullable=False,
                            ),
                        )
                    ),
                ),
            ),
        ),
    )


def _build_implementation(
    simple_registry: StructureRegistry,
    *,
    state_path: str,
    dependencies: tuple[AgentDependencyInput, ...],
) -> ImplementationInput:
    def adjust(exposure: float) -> None:
        """Adjust the exposure of the camera."""

    definition = prepare_definition(
        adjust,
        structure_registry=simple_registry,
        widgets={"exposure": withStateChoices(state_path)},
    )

    return ImplementationInput(
        definition=definition,
        dependencies=dependencies,
        dynamic=False,
        interface="adjust",
        needs_token=True,
    )


def test_state_choice_with_matching_dependency_is_accepted(
    simple_registry: StructureRegistry,
) -> None:
    implementation = _build_implementation(
        simple_registry,
        state_path="camera.state.exposure_ms",
        dependencies=(_camera_dependency(),),
    )

    assert "camera" in {dep.key for dep in implementation.dependencies}
    widget = implementation.definition.args[0].widget
    assert widget is not None
    assert widget.dependency == "camera"


def test_state_choice_without_dependency_is_rejected(
    simple_registry: StructureRegistry,
) -> None:
    with pytest.raises(ValidationError, match="camera"):
        _build_implementation(
            simple_registry,
            state_path="camera.state.exposure_ms",
            dependencies=(),
        )


def test_state_choice_with_mismatched_dependency_is_rejected(
    simple_registry: StructureRegistry,
) -> None:
    other_dependency = AgentDependencyInput(
        key="microscope",
        optional=False,
        auto_resolvable=False,
    )

    with pytest.raises(ValidationError, match="camera"):
        _build_implementation(
            simple_registry,
            state_path="camera.state.exposure_ms",
            dependencies=(other_dependency,),
        )


def test_state_choice_with_unresolvable_field_is_rejected(
    simple_registry: StructureRegistry,
) -> None:
    # The dependency exists and exposes a "state", but not the referenced field.
    with pytest.raises(ValidationError, match="missing_field"):
        _build_implementation(
            simple_registry,
            state_path="camera.state.missing_field",
            dependencies=(_camera_dependency(),),
        )


def test_self_state_choice_needs_no_dependency(
    simple_registry: StructureRegistry,
) -> None:
    # "self." references the function's own state -> dependency is None -> always valid.
    implementation = _build_implementation(
        simple_registry,
        state_path="self.state.exposure_ms",
        dependencies=(),
    )

    widget = implementation.definition.args[0].widget
    assert widget is not None
    assert widget.dependency is None


@declare_state
class CameraState:
    """State exposed by a declared camera protocol dependency."""

    exposure_ms: float = 0.0


@declare(app="lab")
class CameraProtocol:
    """A declared agent protocol exposing a camera state."""

    state: CameraState


def test_register_with_state_choices_exposes_dependency(
    simple_registry: StructureRegistry,
) -> None:
    def adjust(camera: CameraProtocol, exposure: float) -> None:
        """Adjust the exposure of the camera."""

    definition_registry = AppRegistry()
    register_func(
        adjust,
        simple_registry,
        definition_registry,
        RegisterConfig(
            widgets={"exposure": withStateChoices("camera.state.exposure_ms")},
        ),
    )

    implementation = definition_registry.implementations["adjust"]
    assert "camera" in {dep.key for dep in implementation.dependencies}


def test_register_with_unknown_state_choice_dependency_is_rejected(
    simple_registry: StructureRegistry,
) -> None:
    def adjust(camera: CameraProtocol, exposure: float) -> None:
        """Adjust the exposure of the camera."""

    definition_registry = AppRegistry()
    with pytest.raises(ValidationError, match="ghost"):
        register_func(
            adjust,
            simple_registry,
            definition_registry,
            RegisterConfig(
                widgets={"exposure": withStateChoices("ghost.state.exposure_ms")},
            ),
        )
