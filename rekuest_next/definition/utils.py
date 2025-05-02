"""Utils for Rekuest Next"""

import logging
from typing import Any
from rekuest_next.agents.context import is_context
from rekuest_next.api.schema import (
    AssignWidgetInput,
    EffectInput,
    ReturnWidgetInput,
    ValidatorInput,
)
from rekuest_next.definition.errors import DefinitionError
from rekuest_next.state.predicate import is_state

parsers = []

try:
    from annotated_types import Le, Gt, Len

    def extract_annotated_types(
        annotations: list[Any],  # noqa: ANN201
        assign_widget: AssignWidgetInput | None,
        return_widget: ReturnWidgetInput | None,
        validators: list[ValidatorInput] | None,
        effects: list[EffectInput] | None,
        default: Any | None,  # noqa: ANN201, ANN401
        label: str | None,  # noqa: ANN201
        description: str | None,  # noqa: ANN201
    ) -> tuple[
        AssignWidgetInput | None,
        ReturnWidgetInput | None,
        list[ValidatorInput] | None,
        list[EffectInput] | None,
        Any | None,  # noqa: ANN201, ANN401
        str | None,  # noqa: ANN201
        str | None,  # noqa: ANN201
    ]:
        """Extracts the annotated types from the list of annotations."""
        for annotation in annotations:
            if isinstance(annotation, Gt):
                validators.append(
                    ValidatorInput(
                        function=f"(x) => x > {annotation.gt}",
                        label=f"Must be greater than {annotation.gt}",
                        errorMessage=f"Must be greater than {annotation.gt}",
                    )
                )
            if isinstance(annotation, Len):
                validators.append(
                    ValidatorInput(
                        function=f"(x) => x.length > {annotation.max_length} && x.length < {annotation.min_length}",
                        label=f"Must have length inbetween {annotation.max_length} and {annotation.min_length}",
                        errorMessage=f"Must have length inbetween {annotation.max_length} and {annotation.min_length}",
                    )
                )
            if isinstance(annotation, Le):
                validators.append(
                    ValidatorInput(
                        function=f"(x) => x <= {annotation.le}",
                        label=f"Must be less than {annotation.le}",
                        errorMessage=f"Must be less than {annotation.le}",
                    )
                )

        return assign_widget, return_widget, validators, effects, default, label, description

    parsers.append(extract_annotated_types)

except ImportError:
    pass


def is_local_var(type: Any) -> bool:  # noqa: ANN401
    """Check if the type is a local variable."""
    return is_context(type) or is_state(type)


def extract_basic_annotations(
    annotations: list[Any],  # noqa: ANN201
    assign_widget: AssignWidgetInput | None,
    return_widget: ReturnWidgetInput | None,
    validators: list[ValidatorInput] | None,
    effects: list[EffectInput] | None,
    default: Any | None,  # noqa: ANN201, ANN401
    label: str | None,  # noqa: ANN201
    description: str | None,  # noqa: ANN201
) -> tuple[
    AssignWidgetInput | None,
    ReturnWidgetInput | None,
    list[ValidatorInput] | None,
    list[EffectInput] | None,
    Any | None,  # noqa: ANN201, ANN401
    str | None,  # noqa: ANN201
    str | None,  # noqa: ANN201
]:
    """Extracts the basic annotations from the list of annotations.
    This includes the AssignWidget, ReturnWidget, Validators, Effects, Default,
    Label, and Description.
    """

    str_annotation_count = 0

    for annotation in annotations:
        if isinstance(annotation, AssignWidgetInput):
            if assign_widget:
                raise DefinitionError("Multiple AssignWidgets found")
            assign_widget = annotation
        elif isinstance(annotation, ReturnWidgetInput):
            if return_widget:
                raise DefinitionError("Multiple ReturnWidgets found")
            return_widget = annotation
        elif isinstance(annotation, ValidatorInput):
            validators.append(annotation)
        elif isinstance(annotation, EffectInput):
            effects.append(annotation)

        elif hasattr(annotation, "get_assign_widget"):
            if assign_widget:
                raise DefinitionError("Multiple AssignWidgets found")
            assign_widget = annotation.get_assign_widget()
        elif hasattr(annotation, "get_return_widget"):
            if return_widget:
                raise DefinitionError("Multiple ReturnWidgets found")
            return_widget = annotation.get_return_widget()
        elif hasattr(annotation, "get_effects"):
            effects += annotation.get_effects()
        elif hasattr(annotation, "get_default"):
            if default:
                raise DefinitionError("Multiple Defaults found")

            default = annotation.get_default()
        elif hasattr(annotation, "get_validators"):
            validators += annotation.get_validators()
        elif isinstance(annotation, str):
            if str_annotation_count > 0:
                description = annotation
            else:
                label = annotation

            str_annotation_count += 1

        else:
            logging.warning(f"Unrecognized annotation {annotation}")

    return assign_widget, return_widget, validators, effects, default, label, description


parsers.append(extract_basic_annotations)


def extract_annotations(  # noqa: ANN201, D103
    annotations: list[Any],  # noqa: ANN201
    assign_widget: AssignWidgetInput | None,
    return_widget: ReturnWidgetInput | None,
    validators: list[ValidatorInput] | None,
    effects: list[EffectInput] | None,
    default: Any | None,  # noqa: ANN201, ANN401
    label: str | None,  # noqa: ANN201
    description: str | None,  # noqa: ANN201
) -> tuple[
    AssignWidgetInput | None,
    ReturnWidgetInput | None,
    list[ValidatorInput] | None,
    list[EffectInput] | None,
    Any | None,  # noqa: ANN201, ANN401
    str | None,  # noqa: ANN201
    str | None,  # noqa: ANN201
]:
    for parser in parsers:
        assign_widget, return_widget, validators, effects, default, label, description = parser(
            annotations,
            assign_widget,
            return_widget,
            validators,
            effects,
            default,
            label,
            description,
        )

    return assign_widget, return_widget, validators, effects, default, label, description
