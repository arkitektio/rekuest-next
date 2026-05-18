"""Tries to convert an enum to a structure"""

from typing import (
    Any,
    Callable,
    Type,
)
from pydantic import BaseModel
import inspect
from rekuest_next.structures.types import FullFilledEnum
from rekuest_next.api.schema import (
    AssignWidgetInput,
    ReturnWidgetInput,
    ChoiceInput,
    Identifier,
    AssignWidgetKind,
    ReturnWidgetKind,
)
from enum import Enum
from rekuest_next.structures.utils import build_instance_predicate


def cls_to_identifier(cls: Type[Enum]) -> Identifier:
    """Convert a enum class to an identifier string."""
    return Identifier.validate(f"{cls.__module__.lower()}.{cls.__name__.lower()}")


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


class EnumHook(BaseModel):
    """A hook that can be registered to automatically convert enums to structures
    and vice versa.

    Enums will be converted to a structure with a default
    choices widget and a default choices return widget. The shrink and expand
    functions will be generated automatically. The identifier will be generated
    automatically from the class name and module name. The scope will be set to
    global. The predicate will be generated automatically from the class name.


    """

    cls_to_identifier: Callable[[Type[Enum]], Identifier] = cls_to_identifier
    """A hook that can be registered to the structure registry"""

    def is_applicable(self, cls: Type[Any]) -> bool:
        """Given a class, return True if this hook is applicable to it"""
        if inspect.isclass(cls):
            if issubclass(cls, Enum):
                return True
        return False

    def apply(self, cls: Type[object]) -> FullFilledEnum:
        """Apply the hook to the class and return a FullFilledStructure"""
        if not issubclass(cls, Enum):
            raise TypeError(f"{cls} is not a subclass of Enum")

        identifier = self.cls_to_identifier(cls)
        predicate = build_instance_predicate(cls)

        default_widget = AssignWidgetInput(
            kind=AssignWidgetKind.CHOICE,
            choices=tuple(
                [
                    ChoiceInput(label=key, value=key, description=value.__doc__)
                    for key, value in cls.__members__.items()
                ]
            ),
        )
        default_returnwidget = ReturnWidgetInput(
            kind=ReturnWidgetKind.CHOICE,
            choices=tuple(
                [
                    ChoiceInput(label=key, value=key, description=value.__doc__)
                    for key, value in cls.__members__.items()
                ]
            ),
        )

        return FullFilledEnum(
            cls=cls,
            identifier=identifier,
            choices=[
                ChoiceInput(label=key, value=key, description=value.__doc__)
                for key, value in cls.__members__.items()
            ],
            predicate=predicate,
            description=cls.__doc__,
            convert_default=make_enum_converter(cls),
            default_widget=default_widget,
            default_returnwidget=default_returnwidget,
        )
