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
        cls: Type,
        identifier: str = None,
        scope: PortScope = PortScope.LOCAL,
        aexpand: Callable[
            [
                str,
            ],
            Awaitable[Any],
        ] = None,
        ashrink: Callable[
            [
                any,
            ],
            Awaitable[str],
        ] = None,
        acollect: Callable[
            [
                str,
            ],
            Awaitable[Any],
        ] = None,
        predicate: Callable[[Any], bool] = None,
        convert_default: Callable[[Any], str] = None,
        default_widget: Optional[AssignWidgetInput] = None,
        default_returnwidget: Optional[ReturnWidgetInput] = None,
    ) -> FullFilledStructure:
        identifier = identifier or self.cls_to_identifier(cls)
        shrink, expand = build_enum_shrink_expand(cls)
        ashrink = ashrink or shrink
        aexpand = aexpand or expand
        acollect = acollect or void_acollect
        predicate = predicate or build_instance_predicate(cls)
        scope = PortScope.GLOBAL

        default_widget = default_widget or AssignWidgetInput(
            kind=AssignWidgetKind.CHOICE,
            choices=[
                ChoiceInput(label=key, value=key, description=value.__doc__)
                for key, value in cls.__members__.items()
            ],
        )
        default_returnwidget = default_returnwidget or ReturnWidgetInput(
            kind=ReturnWidgetKind.CHOICE,
            choices=[
                ChoiceInput(label=key, value=key, description=value.__doc__)
                for key, value in cls.__members__.items()
            ],
        )

        return FullFilledStructure(
            fullfilled_by="EnumHook",
            cls=cls,
            identifier=identifier,
            scope=scope,
            aexpand=aexpand,
            ashrink=ashrink,
            acollect=acollect,
            predicate=predicate,
            convert_default=convert_default or enum_converter,
            default_widget=default_widget,
            default_returnwidget=default_returnwidget,
        )
