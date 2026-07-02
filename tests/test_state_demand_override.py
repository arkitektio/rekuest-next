"""Tests for the ``demand_state`` marker on agent-dependency protocol attributes.

A ``@declare`` protocol's ``@declare_state`` attributes become state demands. By
default a state demand inherits its ``app`` from the protocol's core app and its
``key`` from the attribute name. An :func:`demand_state` marker (placed in
``typing.Annotated``) redirects it to *another* state.
"""

from typing import Annotated, Any

from rekuest_next import declare, declare_state, demand_state
from rekuest_next.api.schema import AgentDependencyInput, StateDemandInput
from rekuest_next.declare import DeclaredAgentProtocol


def _dependency_of(cls: Any) -> AgentDependencyInput:
    protocol: DeclaredAgentProtocol[Any] = getattr(cls, "__rekuest__dependency__")
    return protocol.to_dependency_input("dep")


def _state_demand_for(
    dependency: AgentDependencyInput, slot_key: str
) -> StateDemandInput:
    (match,) = [d for d in dependency.state_dependencies or () if d.key == slot_key]
    assert match.demand is not None
    return match.demand


def _state_slot_for(dependency: AgentDependencyInput, slot_key: str):
    (match,) = [d for d in dependency.state_dependencies or () if d.key == slot_key]
    return match


def test_state_demand_inherits_app_and_attr_key_by_default() -> None:
    @declare_state
    class CameraState:
        connected: bool

    @declare(app="mymicroscope")
    class Deps:
        camera: CameraState

    dependency = _dependency_of(Deps)
    demanded = _state_demand_for(dependency, "camera")

    assert demanded.app == "mymicroscope"
    assert demanded.key == "camera"
    assert demanded.matches is not None


def test_demand_state_overrides_app_and_key_to_another_state() -> None:
    @declare_state
    class ViewerState:
        open: bool

    @declare(app="mymicroscope")
    class Deps:
        viewer: Annotated[ViewerState, demand_state(app="imagej", key="viewer_state")]

    dependency = _dependency_of(Deps)
    # Slot key stays the attribute name so assignments keep referencing "viewer"...
    demanded = _state_demand_for(dependency, "viewer")
    # ...but the demanded state now points at a different app + key.
    assert demanded.app == "imagej"
    assert demanded.key == "viewer_state"


def test_demand_state_can_pin_by_hash_and_disable_port_matching() -> None:
    @declare_state
    class StatusState:
        ready: bool

    @declare(app="mymicroscope")
    class Deps:
        status: Annotated[StatusState, demand_state(hash="abc123", match_ports=False)]

    dependency = _dependency_of(Deps)
    demanded = _state_demand_for(dependency, "status")

    assert demanded.hash == "abc123"
    assert demanded.matches is None


def test_mixed_default_and_overridden_states_coexist() -> None:
    @declare_state
    class CameraState:
        connected: bool

    @declare_state
    class ViewerState:
        open: bool

    @declare(app="mymicroscope")
    class Deps:
        camera: CameraState
        viewer: Annotated[ViewerState, demand_state(app="imagej", key="viewer_state")]

    dependency = _dependency_of(Deps)

    assert _state_demand_for(dependency, "camera").app == "mymicroscope"
    assert _state_demand_for(dependency, "camera").key == "camera"
    assert _state_demand_for(dependency, "viewer").app == "imagej"
    assert _state_demand_for(dependency, "viewer").key == "viewer_state"


def test_state_slots_are_required_by_default_and_optional_when_marked() -> None:
    @declare_state
    class CameraState:
        connected: bool

    @declare_state
    class TelemetryState:
        uptime: float

    @declare(app="mymicroscope")
    class Deps:
        camera: CameraState
        telemetry: Annotated[TelemetryState, demand_state(optional=True)]

    dependency = _dependency_of(Deps)

    assert _state_slot_for(dependency, "camera").optional is False
    assert _state_slot_for(dependency, "telemetry").optional is True
