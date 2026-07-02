"""Parsers that turn ``Annotated[...]`` metadata into port-building fields.

A port's extra metadata (description, default, widgets, validators, effects,
requires/provides, proposed units) can be supplied as markers inside
:data:`typing.Annotated`. :func:`extract_annotations` runs every registered
parser over those markers and accumulates the result into a single
:class:`PortAnnotations` dataclass, which the port converters in
:mod:`rekuest_next.definition.define` then read by name.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from rekuest_next.annotations.markers import Default, Description, Units
from rekuest_next.api.schema import (
    AssignWidgetInput,
    EffectInput,
    ProvidesInput,
    RequiresInput,
    ReturnWidgetInput,
    ValidatorInput,
)
from rekuest_next.definition.errors import DefinitionError


@dataclass
class PortAnnotations:
    """Accumulated port-building fields extracted from ``Annotated`` markers.

    Each parser reads the markers on a port and fills the relevant fields. The
    converters in :mod:`rekuest_next.definition.define` seed an instance with the
    values known so far and read the fields back by name after parsing.
    """

    default: Any | None = None  # noqa: ANN401
    label: str | None = None
    description: str | None = None
    assign_widget: AssignWidgetInput | None = None
    return_widget: ReturnWidgetInput | None = None
    validators: list[ValidatorInput] = field(default_factory=list)
    effects: list[EffectInput] = field(default_factory=list)
    requires: list[RequiresInput] | None = None
    provides: list[ProvidesInput] | None = None
    proposed_units: list[str] | None = None


# Registered parsers. Each takes the raw ``Annotated`` markers plus the
# accumulator and returns the (possibly mutated) accumulator.
parsers: list[Callable[[list[Any], PortAnnotations], PortAnnotations]] = []


def extract_basic_annotations(
    annotations: list[Any],
    acc: PortAnnotations,
) -> PortAnnotations:
    """Extracts basic Rekuest annotations like widgets, validators, and strings."""

    for annotation in annotations:
        match annotation:
            case Units():
                if acc.proposed_units is not None:
                    raise DefinitionError("Multiple Units found")
                acc.proposed_units = list(annotation.units)

            case AssignWidgetInput():
                if acc.assign_widget:
                    raise DefinitionError("Multiple AssignWidgets found")
                acc.assign_widget = annotation

            case ReturnWidgetInput():
                if acc.return_widget:
                    raise DefinitionError("Multiple ReturnWidgets found")
                acc.return_widget = annotation

            case ValidatorInput():
                acc.validators.append(annotation)

            case EffectInput():
                acc.effects.append(annotation)

            case RequiresInput():
                if acc.requires is None:
                    acc.requires = []
                acc.requires.append(annotation)

            case ProvidesInput():
                if acc.provides is None:
                    acc.provides = []
                acc.provides.append(annotation)

            case Description():
                if acc.description:
                    raise DefinitionError("Multiple descriptions found")
                acc.description = annotation.value

            case Default():
                if acc.default is not None:
                    raise DefinitionError("Multiple default values found")
                acc.default = annotation.value

            case _:
                pass

    return acc


# Register built-in parser
parsers.append(extract_basic_annotations)


# Optional: parser using `annotated_types`
try:
    from annotated_types import Gt, Le, Len

    def extract_annotated_types(
        annotations: list[Any],
        acc: PortAnnotations,
    ) -> PortAnnotations:
        """Extracts annotated types from `annotated_types`."""

        for annotation in annotations:
            match annotation:
                case Gt(gt):
                    acc.validators.append(
                        ValidatorInput(
                            function=f"(x) => x > {gt}",  # type: ignore
                            label=f"Must be greater than {gt}",
                            errorMessage=f"Must be greater than {gt}",
                        )
                    )
                case Le(le):
                    acc.validators.append(
                        ValidatorInput(
                            function=f"(x) => x <= {le}",  # type: ignore
                            label=f"Must be less than {le}",
                            errorMessage=f"Must be less than {le}",
                        )
                    )
                case Len(min_length=min_len, max_length=max_len):
                    acc.validators.append(
                        ValidatorInput(
                            function=f"(x) => x.length >= {min_len} && x.length <= {max_len}",  # type: ignore
                            label=f"Must have length between {min_len} and {max_len}",
                            errorMessage=f"Must have length between {min_len} and {max_len}",
                        )
                    )
                case _:
                    pass

        return acc

    parsers.append(extract_annotated_types)

except ImportError:
    logging.info("annotated_types not available, skipping related parser.")


def extract_annotations(
    annotations: list[Any],
    base: PortAnnotations | None = None,
) -> PortAnnotations:
    """Run all registered parsers to extract semantic Rekuest annotations.

    Args:
        annotations: The metadata markers pulled from an ``Annotated[...]`` hint.
        base: The values already known for the port (defaults, label, widgets the
            converter was called with). Parsers accumulate onto a copy of this.

    Returns:
        The populated :class:`PortAnnotations` accumulator.
    """
    acc = base or PortAnnotations()

    for parser in parsers:
        acc = parser(annotations, acc)

    return acc
