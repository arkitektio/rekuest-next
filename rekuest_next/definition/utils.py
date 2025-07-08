"""Utils for Rekuest Next"""

import logging
from typing import Any, Callable, TypeAlias

from rekuest_next.agents.context import is_context
from rekuest_next.api.schema import (
    AssignWidgetInput,
    EffectInput,
    ReturnWidgetInput,
    ValidatorInput,
)
from rekuest_next.definition.errors import DefinitionError
from rekuest_next.state.predicate import is_state
from rekuest_next.structures.types import JSONSerializable

# Type alias for annotation parser return type
AnnotationResult: TypeAlias = tuple[
    Any | None,
    str | None,
    str | None,
    AssignWidgetInput | None,
    ReturnWidgetInput | None,
    list[ValidatorInput],
    list[EffectInput],
]

# Registered parsers
parsers: list[Callable[[list[Any], *AnnotationResult], AnnotationResult]] = []


class DescriptionAddin:
    """A string that can be used to add a description to a function or method."""

    def __init__(self, value: str) -> None:
        """Initialize the DescriptionAddin with a value."""
        if not isinstance(value, str):  # type: ignore
            raise TypeError("DescriptionAddin value must be a string")
        self.value = value

    def __repr__(self) -> str:
        """Return a string representation of the DescriptionAddin."""
        return f"Description({self.value})"


class DefaultAddin:
    """A default value that can be used to add a default value to a function or method."""

    def __init__(self, value: JSONSerializable) -> None:
        """Initialize the DefaultAddin with a value."""
        self.value = value

    def __repr__(self) -> str:
        """Return a string representation of the DefaultAddin."""
        return f"Default(value={self.value})"


def is_local_var(type_: Any) -> bool:  # noqa: ANN401
    """Check if the type is a local variable (context or state)."""
    return is_context(type_) or is_state(type_)


def extract_basic_annotations(
    annotations: list[Any],
    default: Any | None,
    label: str | None,
    description: str | None,
    assign_widget: AssignWidgetInput | None,
    return_widget: ReturnWidgetInput | None,
    validators: list[ValidatorInput],
    effects: list[EffectInput],
) -> AnnotationResult:
    """Extracts basic Rekuest annotations like widgets, validators, and strings."""

    for annotation in annotations:
        match annotation:
            case AssignWidgetInput():
                if assign_widget:
                    raise DefinitionError("Multiple AssignWidgets found")
                assign_widget = annotation

            case ReturnWidgetInput():
                if return_widget:
                    raise DefinitionError("Multiple ReturnWidgets found")
                return_widget = annotation

            case ValidatorInput():
                validators.append(annotation)

            case EffectInput():
                effects.append(annotation)

            case DescriptionAddin():
                if description:
                    raise DefinitionError("Multiple descriptions found")
                description = annotation.value

            case DefaultAddin():
                if default is not None:
                    raise DefinitionError("Multiple default values found")
                default = annotation.value

            case _:
                pass

    return (
        default,
        label,
        description,
        assign_widget,
        return_widget,
        validators,
        effects,
    )


# Register built-in parser
parsers.append(extract_basic_annotations)


# Optional: parser using `annotated_types`
try:
    from annotated_types import Le, Gt, Len

    def extract_annotated_types(
        annotations: list[Any],
        default: Any | None,  # noqa: ANN401
        label: str | None,
        description: str | None,
        assign_widget: AssignWidgetInput | None,
        return_widget: ReturnWidgetInput | None,
        validators: list[ValidatorInput],
        effects: list[EffectInput],
    ) -> AnnotationResult:
        """Extracts annotated types from `annotated_types`."""

        for annotation in annotations:
            match annotation:
                case Gt(gt):
                    validators.append(
                        ValidatorInput(
                            function=f"(x) => x > {gt}",  # type: ignore
                            label=f"Must be greater than {gt}",
                            errorMessage=f"Must be greater than {gt}",
                        )
                    )
                case Le(le):
                    validators.append(
                        ValidatorInput(
                            function=f"(x) => x <= {le}",  # type: ignore
                            label=f"Must be less than {le}",
                            errorMessage=f"Must be less than {le}",
                        )
                    )
                case Len(min_length=min_len, max_length=max_len):
                    validators.append(
                        ValidatorInput(
                            function=f"(x) => x.length >= {min_len} && x.length <= {max_len}",  # type: ignore
                            label=f"Must have length between {min_len} and {max_len}",
                            errorMessage=f"Must have length between {min_len} and {max_len}",
                        )
                    )
                case _:
                    pass

        return (
            default,
            label,
            description,
            assign_widget,
            return_widget,
            validators,
            effects,
        )

    parsers.append(extract_annotated_types)

except ImportError:
    logging.info("annotated_types not available, skipping related parser.")


def extract_annotations(
    annotations: list[Any],
    default: Any | None = None,  # noqa: ANN401
    label: str | None = None,
    description: str | None = None,
    assign_widget: AssignWidgetInput | None = None,
    return_widget: ReturnWidgetInput | None = None,
    validators: list[ValidatorInput] | None = None,
    effects: list[EffectInput] | None = None,
) -> AnnotationResult:
    """Runs all registered parsers to extract semantic Rekuest annotations."""
    validators = validators or []
    effects = effects or []

    for parser in parsers:
        (
            default,
            label,
            description,
            assign_widget,
            return_widget,
            validators,
            effects,
        ) = parser(
            annotations,
            default,
            label,
            description,
            assign_widget,
            return_widget,
            validators,
            effects,
        )

    return (
        default,
        label,
        description,
        assign_widget,
        return_widget,
        validators,
        effects,
    )
