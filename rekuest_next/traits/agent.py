from typing import TYPE_CHECKING, Iterable, Iterator

from pydantic import BaseModel, model_validator

if TYPE_CHECKING:
    from rekuest_next.api.schema import (
        ArgPortInput,
        AssignWidgetInput,
        ImplementAgentInput,
    )


def _iter_state_choice_widgets(
    ports: "Iterable[ArgPortInput]",
) -> "Iterator[tuple[ArgPortInput, AssignWidgetInput]]":
    """Yield every ``STATE_CHOICE`` widget reachable from a set of ports."""
    for port in ports or ():
        widget = port.widget
        # ``use_enum_values=True`` stores the kind as the plain string.
        if widget is not None and widget.kind == "STATE_CHOICE":
            yield port, widget
        yield from _iter_state_choice_widgets(port.children or ())


def _ensure_unique(values: Iterable[str], label: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"Duplicate {label} '{value}' in agent input")
        seen.add(value)


class ImplementAgentInputTrait(BaseModel):
    """Validation over the whole assembled agent input.

    Runs once on the complete payload, so it can resolve ``self`` state choice
    references against the agent's own states and check cross-implementation
    invariants that a single ``ImplementationInput`` cannot see.
    """

    @model_validator(mode="after")  # type: ignore[override]
    def validate_agent_input(
        self: "ImplementAgentInput",
    ) -> "ImplementAgentInput":
        """Validate self-state references and structural payload invariants."""
        implementations = tuple(self.implementations or ())
        states = tuple(self.states or ())
        locks = tuple(self.locks or ())

        # 1. Resolve `self` STATE_CHOICE references against the agent's own states.
        from rekuest_next.blok.parser import resolve_state_reference

        for implementation in implementations:
            dependencies = tuple(implementation.dependencies or ())
            name = implementation.interface or implementation.definition.name
            for port, widget in _iter_state_choice_widgets(
                implementation.definition.args or ()
            ):
                if widget.dependency is None and widget.state_path is not None:
                    resolve_state_reference(
                        None,
                        widget.state_path,
                        dependencies=dependencies,
                        own_states=states,
                        context=(
                            f"state choice widget for port '{port.key}' in "
                            f"implementation '{name}'"
                        ),
                    )

        # 2. Implementation interfaces must be unique.
        _ensure_unique(
            (
                implementation.interface or implementation.definition.name
                for implementation in implementations
            ),
            "implementation interface",
        )

        # 3. State interfaces must be unique.
        _ensure_unique((state.interface for state in states), "state interface")

        # 4. Every referenced lock must be provided.
        lock_keys = {lock.key for lock in locks}
        for implementation in implementations:
            name = implementation.interface or implementation.definition.name
            for lock in implementation.locks or ():
                if lock not in lock_keys:
                    raise ValueError(
                        f"Implementation '{name}' references lock '{lock}' that is "
                        f"not provided. Available locks: {sorted(lock_keys)}"
                    )

        return self
