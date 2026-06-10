"""Converters that turn plain Python classes into FullFilled types.

These implement the auto-registration dispatch of the structure registry:
enums become FullFilledEnum, classes implementing the global structure
protocol (get_identifier/ashrink/aexpand) become FullFilledStructure, and
everything else becomes a FullFilledMemoryStructure kept in the local shelve.
"""

from enum import Enum
from typing import (
    Any,
    Callable,
    Type,
)

from rekuest_next.api.schema import (
    AssignWidgetInput,
    AssignWidgetKind,
    ChoiceInput,
    Identifier,
    ReturnWidgetInput,
    ReturnWidgetKind,
)
from rekuest_next.structures.errors import StructureDefinitionError
from rekuest_next.structures.types import (
    FullFilledEnum,
    FullFilledMemoryStructure,
    FullFilledStructure,
)
from rekuest_next.structures.utils import build_instance_predicate


def cls_to_identifier(cls: Type[Any]) -> Identifier:
    """Derive an identifier string from a class's module and name."""
    try:
        return Identifier.validate(f"{cls.__module__.lower()}.{cls.__name__.lower()}")
    except AttributeError as e:
        raise StructureDefinitionError(
            f"Cannot convert {cls} to identifier. The class needs to have a"
            " __module__ and __name__ attribute."
        ) from e


def identity_default_converter(x: str) -> str:
    """Convert a value to its string representation."""
    return x


def make_enum_converter(cls: Type[Enum]) -> Callable[[Any], str]:
    """Create a converter that maps a default value to its enum member name.

    Handles both enum instances and raw values (e.g. functools.partial treated
    as a descriptor in Python 3.13+ so it bypasses normal Enum member wrapping).
    """

    def converter(value: Any) -> str:
        if isinstance(value, cls):
            return value.name
        # Fallback: search registered members by .value first.
        for member in cls:
            if member.value is value or member.value == value:
                return member.name
        # Last resort: scan class attributes directly (Python 3.13+ descriptor
        # behaviour means partial-valued members never appear in __members__).
        for attr_name, attr_val in vars(cls).items():
            if attr_name.startswith("_"):
                continue
            if attr_val is value or attr_val == value:
                return attr_name
        raise ValueError(f"Cannot convert {value!r} to an enum name for {cls}")

    return converter


def enum_choices(cls: Type[Enum]) -> list[ChoiceInput]:
    """Build the ChoiceInput list for an enum's members."""
    return [
        ChoiceInput(label=key, value=key, description=value.__doc__)
        for key, value in cls.__members__.items()
    ]


def is_global_structure(cls: Type[Any]) -> bool:
    """Check whether a class implements the global structure protocol."""
    return (
        hasattr(cls, "get_identifier")
        and hasattr(cls, "aexpand")
        and hasattr(cls, "ashrink")
    )


def fullfilled_enum_from_cls(cls: Type[Enum]) -> FullFilledEnum:
    """Build a FullFilledEnum from an Enum subclass."""
    choices = enum_choices(cls)

    return FullFilledEnum(
        cls=cls,
        identifier=cls_to_identifier(cls),
        choices=choices,
        predicate=build_instance_predicate(cls),
        description=cls.__doc__,
        convert_default=make_enum_converter(cls),
        default_widget=AssignWidgetInput(
            kind=AssignWidgetKind.CHOICE, choices=tuple(choices)
        ),
        default_returnwidget=ReturnWidgetInput(
            kind=ReturnWidgetKind.CHOICE, choices=tuple(choices)
        ),
    )


def fullfilled_structure_from_cls(cls: Type[Any]) -> FullFilledStructure:
    """Build a FullFilledStructure from a class implementing the global
    structure protocol (get_identifier/ashrink/aexpand)."""
    if not hasattr(cls, "get_identifier"):
        raise StructureDefinitionError(
            f"Class {cls} does not have a get_identifier method"
        )

    return FullFilledStructure(
        cls=cls,
        identifier=cls.get_identifier(),
        aexpand=getattr(cls, "aexpand"),
        ashrink=getattr(cls, "ashrink"),
        predicate=getattr(cls, "predicate", None) or build_instance_predicate(cls),
        description=None,
        convert_default=getattr(cls, "convert_default", identity_default_converter),
        default_widget=cls.get_default_widget()
        if hasattr(cls, "get_default_widget")
        else None,
        default_returnwidget=cls.get_default_returnwidget()
        if hasattr(cls, "get_default_returnwidget")
        else None,
    )


def fullfilled_memory_structure_from_cls(
    cls: Type[Any],
) -> FullFilledMemoryStructure:
    """Build a FullFilledMemoryStructure for a class kept in the local shelve."""
    if hasattr(cls, "get_identifier"):
        identifier = cls.get_identifier()
    else:
        identifier = cls_to_identifier(cls)

    return FullFilledMemoryStructure(
        cls=cls,
        identifier=identifier,
        predicate=build_instance_predicate(cls),
        description=None,
    )
