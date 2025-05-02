"""Tries to convert an enum to a structure"""

from typing import (
    Any,
    Awaitable,
    Callable,
    Optional,
    Type,
)
from pydantic import BaseModel
import inspect
from rekuest_next.structures.types import FullFilledStructure
from rekuest_next.api.schema import (
    PortScope,
    AssignWidgetInput,
    ReturnWidgetInput,
    ChoiceInput,
    Identifier,
    AssignWidgetKind,
    ReturnWidgetKind,
)
from enum import Enum


def build_enum_shrink_expand(cls: Type[Enum]):
    async def shrink(s):
        return s.name

    async def expand(v):
        return cls.__members__[v]

    return shrink, expand


def cls_to_identifier(cls: Type) -> Identifier:
    return f"{cls.__module__.lower()}.{cls.__name__.lower()}"


def build_instance_predicate(cls: Type):
    return lambda x: isinstance(x, cls)


def enum_converter(x):
    return x.name


async def void_acollect(id: str):
    return None


class EnumHook(BaseModel):
    cls_to_identifier: Callable[[Type], Identifier] = cls_to_identifier
    """A hook that can be registered to the structure registry"""

    def is_applicable(self, cls: Type) -> bool:
        """Given a class, return True if this hook is applicable to it"""
        if inspect.isclass(cls):
            if issubclass(cls, Enum):
                return True
        return False

    def apply(
        self,
        cls: Type
    ) -> FullFilledStructure:
        identifier = self.cls_to_identifier(cls)
        ashrink, aexpand = build_enum_shrink_expand(cls)
        predicate = build_instance_predicate(cls)
        scope = PortScope.GLOBAL

        default_widget = AssignWidgetInput(
            kind=AssignWidgetKind.CHOICE,
            choices=tuple([
                ChoiceInput(label=key, value=key, description=value.__doc__)
                for key, value in cls.__members__.items()
            ])
        )
        default_returnwidget = ReturnWidgetInput(
            kind=ReturnWidgetKind.CHOICE,
            choices=tuple([
                ChoiceInput(label=key, value=key, description=value.__doc__)
                for key, value in cls.__members__.items()
            ])
        )

        return FullFilledStructure(
            cls=cls,
            identifier=identifier,
            scope=scope,
            aexpand=aexpand,
            ashrink=ashrink,
            predicate=predicate,
            convert_default=enum_converter,
            default_widget=default_widget,
            default_returnwidget=default_returnwidget,
        )
