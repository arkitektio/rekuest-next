"""Traits for ports and widgets, especially for validating the input"""

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any
from pydantic import BaseModel, field_validator, model_validator

from rekuest_next.traits.calls import check_pure_call

from rekuest_next.messages import JSONSerializable

if TYPE_CHECKING:
    from rekuest_next.api.schema import (
        PortInput,
        DefinitionInput,
        EffectInput,
        ValidatorInput,
        SearchAssignWidgetInput,
        SliderAssignWidgetInput,
        StateChoiceAssignWidgetInput,
    )


class PortTrait(BaseModel):
    """
    Class for validating port input
    on the client side

    """

    @field_validator("default", check_fields=False)
    def default_validator(v: Any) -> JSONSerializable:  # noqa: ANN401
        """Validate the default value of the port"""
        # Check if the default value is JSON serializable
        if v is None:
            return v

        if not isinstance(v, (str, int, float, dict, list, bool)):
            raise ValueError(
                "Default value must be JSON serializable, got: " + str(v)
            ) from None

        return v  # type: ignore[return-value]

    @model_validator(mode="after")  # type: ignore[override]
    def validate_portkind_nested(self: "PortInput") -> "PortInput":
        """Validate the function of the validator"""
        from rekuest_next.api.schema import PortKind

        if self.kind == PortKind.STRUCTURE:
            if self.identifier is None:
                raise ValueError(
                    "When specifying a structure you need to provide an arkitekt identifier got:"
                )

        if self.kind == PortKind.QUANTITY:
            if not self.reference_unit:
                raise ValueError(
                    "When specifying a quantity you need to provide a 'reference_unit' "
                    "(e.g. 'volt'). It is the default selection and other units of the same "
                    "dimension are still allowed."
                )

        if self.kind == PortKind.LIST:
            if self.children is None:
                raise ValueError(
                    "When specifying a list you need to provide a wrapped 'children' port"
                )
            assert len(self.children) == 1, "List can only have one child"

        if self.kind == PortKind.DICT:
            if self.children is None:
                raise ValueError(
                    "When specifying a dict you need to provide a wrapped 'children' port"
                )
            assert len(self.children) == 1, (
                "Dict can only one child (key is always strings)"
            )

        return self


PORT_PATH_SEPARATOR = ".."
"""Separator of a port path: ``foo..bar`` is the child ``bar`` of port ``foo``."""

def _kind_name(kind: Any) -> str:  # noqa: ANN401
    return getattr(kind, "value", kind)


def _resolve_port_path(path: str, ports: "list[PortInput] | tuple[PortInput, ...]") -> bool:
    """True if a port path (``a..b..c``) resolves through ``children`` from the given roots."""
    candidates = list(ports)
    for segment in path.split(PORT_PATH_SEPARATOR):
        match = next((port for port in candidates if port.key == segment), None)
        if match is None:
            return False
        candidates = list(match.children or ())
    return True


class SearchWidgetInputTrait(BaseModel):
    """Client-side checks for a SEARCH assign widget: every query variable is backed by a filter or dependency."""

    @model_validator(mode="after")  # type: ignore[override]
    def validate_query_variables(self: "SearchAssignWidgetInput") -> "SearchAssignWidgetInput":
        """Validate the search query against the filters and dependencies"""
        from rekuest_next.scalars import (
            RESERVED_SEARCH_VARIABLES,
            get_search_query_variables,
        )

        if self.query is None:
            raise ValueError(
                "When specifying a SearchWidget you need to provide an query parameter"
            )

        filter_keys = {f.key for f in (self.filters or [])}
        dependency_keys = set(self.dependencies or [])
        available = filter_keys | dependency_keys

        for variable in get_search_query_variables(self.query):
            if variable in RESERVED_SEARCH_VARIABLES:
                continue
            if variable not in available:
                raise ValueError(
                    f"Search query variable '${variable}' is not backed by a filter port"
                    f" or a dependency. Available filters: {sorted(filter_keys)},"
                    f" dependencies: {sorted(dependency_keys)}"
                )

        return self


class SliderWidgetInputTrait(BaseModel):
    """Client-side checks for a SLIDER assign widget: both bounds given and ordered."""

    @model_validator(mode="after")  # type: ignore[override]
    def validate_bounds(self: "SliderAssignWidgetInput") -> "SliderAssignWidgetInput":
        """Validate the slider bounds"""
        if self.min is None or self.max is None:
            raise ValueError(
                "When specifying a Slider you need to provide an 'max and 'min' parameter"
            )

        if self.min > self.max:
            raise ValueError(
                "When specifying a Slider you need to provide an 'max' greater than 'min'"
            )

        return self


class StateChoiceWidgetInputTrait(BaseModel):
    """Client-side checks for a STATE_CHOICE assign widget: exactly one pointer form."""

    @model_validator(mode="after")  # type: ignore[override]
    def validate_pointer(self: "StateChoiceAssignWidgetInput") -> "StateChoiceAssignWidgetInput":
        """Validate that exactly one of state_path or state_call is set"""
        if (self.state_path is None) == (self.state_call is None):
            raise ValueError(
                "STATE_CHOICE widget needs exactly one of state_path or state_call"
            )
        return self


class ValidatorInputTrait(BaseModel):
    """An addin trait that rejects impure validator calls before upload.

    Mirrors the server rule: the call may not contain agent calls and every
    ``value_path`` must be rooted at ``value`` or at a declared dependency.
    """

    @model_validator(mode="after")  # type: ignore[override]
    def check_call_is_pure(self: "ValidatorInput") -> "ValidatorInput":
        """Validate the call of the validator"""
        check_pure_call(
            self.call,
            self.dependencies,
            f"Validator {self.label or self.call.operation}",
        )
        return self


class EffectInputTrait(BaseModel):
    """An addin trait that rejects impure effect calls before upload.

    Mirrors the server rule: the call may not contain agent calls and every
    ``value_path`` must be rooted at ``value`` or at a declared dependency.
    """

    @model_validator(mode="after")  # type: ignore[override]
    def check_call_is_pure(self: "EffectInput") -> "EffectInput":
        """Validate the call of the effect"""
        check_pure_call(
            self.call,
            self.dependencies,
            f"Effect {self.kind} ({self.call.operation})",
        )
        return self


class DefinitionInputTrait(BaseModel):
    """An addin trait for validating the input of a definition"""

    @model_validator(mode="after")  # type: ignore[override]
    def check_dependencies(self: "DefinitionInput") -> "DefinitionInput":
        """Every dependency of every widget, validator and effect is a resolvable port path.

        Mirrors the server rule: args, returns, nested children and port groups are
        walked; a dependency is a port path (``foo..bar`` is the child ``bar`` of port
        ``foo``) resolved from the top-level args and returns. Inside a call the root
        ``value`` always names the port's own value, so a sibling port called ``value``
        is shadowed there (but is otherwise an ordinary port).
        """
        from rekuest_next.api.schema import AssignWidgetKind

        roots = [*(self.args or ()), *(self.returns or ())]

        def check(dependencies: "tuple[str, ...] | None", owner: str) -> None:
            for dep in dependencies or ():
                if not _resolve_port_path(dep, roots):
                    raise ValueError(f"{owner} has invalid dependency: {dep}")

        def walk(ports: "Iterable[Any]", prefix: str = "") -> None:
            for port in ports:
                path = f"{prefix}{port.key}"
                widget = getattr(port, "widget", None)
                if (
                    widget is not None
                    and _kind_name(widget.kind) == AssignWidgetKind.SEARCH.value
                    and widget.dependencies
                ):
                    check(widget.dependencies, f"Search widget in port {path}")

                # Only arg ports carry validators.
                for validator in getattr(port, "validators", None) or ():
                    check(
                        validator.dependencies,
                        f"Validator {validator.label or validator.call.operation} in port {path}",
                    )
                for effect in port.effects or ():
                    check(
                        effect.dependencies,
                        f"Effect {_kind_name(effect.kind)} ({effect.call.operation}) in port {path}",
                    )
                walk(port.children or (), f"{path}{PORT_PATH_SEPARATOR}")

        walk(self.args or ())
        walk(self.returns or ())
        for group in self.port_groups or ():
            for effect in group.effects or ():
                check(
                    effect.dependencies,
                    f"Effect {_kind_name(effect.kind)} ({effect.call.operation}) in port group {group.key}",
                )

        return self
