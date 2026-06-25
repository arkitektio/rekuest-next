from typing import TYPE_CHECKING

from pydantic import BaseModel, model_validator

if TYPE_CHECKING:
    from rekuest_next.api.schema import (
        AgentDependencyInput,
        ArgPortInput,
        ImplementationInput,
    )


def _validate_port_state_choices(
    port: "ArgPortInput",
    dependencies: "tuple[AgentDependencyInput, ...]",
) -> None:
    """Validate the state choice widgets of a port (and its children).

    A ``STATE_CHOICE`` widget (created via
    :func:`rekuest_next.widgets.withStateChoices`) references a state through a
    ``dependency`` and a ``state_path``. A **named** dependency reference must be
    resolvable through that dependency's declared ``state_demands``. A ``self``
    reference (``dependency is None``) is resolved against the agent's own states
    on the assembled ``ImplementAgentInput`` instead, so it is skipped here.
    """
    widget = port.widget
    # ``use_enum_values=True`` stores the kind as the plain string "STATE_CHOICE".
    if (
        widget is not None
        and widget.kind == "STATE_CHOICE"
        and widget.dependency is not None
        and widget.state_path is not None
    ):
        from rekuest_next.blok.parser import resolve_state_reference

        resolve_state_reference(
            widget.dependency,
            widget.state_path,
            dependencies=dependencies,
            own_states=(),
            context=f"state choice widget for port '{port.key}'",
        )

    for child in port.children or ():
        _validate_port_state_choices(child, dependencies)


class ImplementationInputTrait(BaseModel):
    """Client side validation for an ``ImplementationInput``."""

    @model_validator(mode="after")  # type: ignore[override]
    def validate_state_choice_dependencies(
        self: "ImplementationInput",
    ) -> "ImplementationInput":
        """Ensure named state choice widgets resolve through their dependencies."""
        dependencies = tuple(self.dependencies or ())

        for port in self.definition.args or ():
            _validate_port_state_choices(port, dependencies)

        return self
