"""Tests for the ``demand`` decorator on agent-dependency protocol methods.

A ``@declare`` protocol method becomes an action demand. By default that demand
inherits its ``app`` from the protocol's core app and its ``key`` from the method
name. Applying :func:`demand` to a method redirects it to *another* action.
"""

from typing import Any

from rekuest_next import declare, demand
from rekuest_next.api.schema import ActionDemandInput, AgentDependencyInput
from rekuest_next.declare import DeclaredAgentProtocol


def _dependency_of(cls: Any) -> AgentDependencyInput:
    protocol: DeclaredAgentProtocol[Any] = getattr(cls, "__rekuest__dependency__")
    return protocol.to_dependency_input("dep")


def _demand_for(dependency: AgentDependencyInput, slot_key: str) -> ActionDemandInput:
    (match,) = [d for d in dependency.action_dependencies or () if d.key == slot_key]
    assert match.demand is not None
    return match.demand


def _slot_for(dependency: AgentDependencyInput, slot_key: str):
    (match,) = [d for d in dependency.action_dependencies or () if d.key == slot_key]
    return match


def test_action_demand_inherits_app_and_method_key_by_default() -> None:
    @declare(app="mymicroscope")
    class Deps:
        def acquire(self, exposure: float) -> bytes:  # noqa: D401
            """Acquire a frame."""
            return b""

    dependency = _dependency_of(Deps)

    # The agent dependency carries the protocol's core app...
    assert dependency.app == "mymicroscope"

    # ...and the action demand inherits app + method-name-as-key.
    demanded = _demand_for(dependency, "acquire")
    assert demanded.app == "mymicroscope"
    assert demanded.key == "acquire"
    # Structural matching is still emitted by default.
    assert demanded.arg_matches is not None


def test_demand_overrides_app_and_key_to_another_action() -> None:
    @declare(app="mymicroscope")
    class Deps:
        @demand(app="imagej", key="open_image")
        def open(self, path: str) -> bytes:
            return b""

    dependency = _dependency_of(Deps)

    # Slot key stays the method name so assignments keep referencing "open"...
    demanded = _demand_for(dependency, "open")
    # ...but the demanded action now points at a different app + key.
    assert demanded.app == "imagej"
    assert demanded.key == "open_image"


def test_demand_can_pin_by_hash_and_disable_port_matching() -> None:
    @declare(app="mymicroscope")
    class Deps:
        @demand(hash="abc123", match_ports=False)
        def snap(self, exposure: float) -> bytes:
            return b""

    dependency = _dependency_of(Deps)
    demanded = _demand_for(dependency, "snap")

    assert demanded.hash == "abc123"
    assert demanded.arg_matches is None
    assert demanded.return_matches is None
    # A hash-pinned demand should not over-constrain with the local name.
    assert demanded.name is None


def test_mixed_default_and_overridden_methods_coexist() -> None:
    @declare(app="mymicroscope")
    class Deps:
        def acquire(self, exposure: float) -> bytes:
            return b""

        @demand(app="imagej", key="open_image")
        def open(self, path: str) -> bytes:
            return b""

    dependency = _dependency_of(Deps)

    assert _demand_for(dependency, "acquire").app == "mymicroscope"
    assert _demand_for(dependency, "acquire").key == "acquire"
    assert _demand_for(dependency, "open").app == "imagej"
    assert _demand_for(dependency, "open").key == "open_image"


def test_action_slots_are_required_by_default_and_optional_when_marked() -> None:
    @declare(app="mymicroscope")
    class Deps:
        def acquire(self, exposure: float) -> bytes:
            return b""

        @demand(optional=True)
        def autofocus(self) -> None:
            return None

    dependency = _dependency_of(Deps)

    assert _slot_for(dependency, "acquire").optional is False
    assert _slot_for(dependency, "autofocus").optional is True


def test_optional_composes_with_app_key_redirect() -> None:
    @declare(app="mymicroscope")
    class Deps:
        @demand(app="imagej", key="open_image", optional=True)
        def open(self, path: str) -> bytes:
            return b""

    dependency = _dependency_of(Deps)

    slot = _slot_for(dependency, "open")
    assert slot.optional is True
    assert slot.demand is not None
    assert slot.demand.app == "imagej"
    assert slot.demand.key == "open_image"
