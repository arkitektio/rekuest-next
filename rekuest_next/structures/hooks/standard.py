from typing import (
    Any,
    Awaitable,
    Callable,
    Optional,
    Type,
)
from pydantic import BaseModel
from rekuest_next.structures.types import FullFilledStructure
from rekuest_next.api.schema import (
    PortScope,
    AssignWidgetInput,
    ReturnWidgetInput,
    Identifier,
)
from rekuest_next.collection.shelve import get_current_shelve
from .errors import HookError


async def id_shrink(self):
    return self.id


async def shelve_ashrink(cls: Type):
    shelve = get_current_shelve()
    return await shelve.aput(cls)


async def shelve_aexpand(id: str):
    shelve = get_current_shelve()
    return await shelve.aget(id)


async def shelve_acollect(id: str):
    shelve = get_current_shelve()
    return await shelve.adelete(id)


def identity_default_converter(x):
    return x


def cls_to_identifier(cls: Type) -> Identifier:
    return f"{cls.__module__.lower()}.{cls.__name__.lower()}"


def build_instance_predicate(cls: Type):
    return lambda x: isinstance(x, cls)


async def void_acollect(id: str):
    return None


class StandardHookError(HookError):
    pass


class StandardHook(BaseModel):
    cls_to_identifier: Callable[[Type], Identifier] = cls_to_identifier
    """The Standard Hook is a hook that can be registered to the structure registry.

    It will register all local structures in a shelve and will use the shelve to
    expand and shrink the structures. All global structures will net to defined aexpand and
    ashrink using the methods defined in the structure.

    """

    def is_applicable(self, cls: Type) -> bool:
        """Given a class, return True if this hook is applicable to it"""
        return True  # Catch all

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
        if identifier is None:
            identifier = self.cls_to_identifier(cls)

        if convert_default is None:
            if hasattr(cls, "convert_default"):
                convert_default = cls.convert_default
            convert_default = identity_default_converter

        if aexpand is None:
            if not hasattr(cls, "aexpand") and scope == PortScope.GLOBAL:
                raise StandardHookError(
                    f"You need to pass 'expand' method or {cls} needs to implement a"
                    " aexpand method if it wants to become a GLOBAL structure"
                )
            aexpand = getattr(cls, "aexpand", shelve_aexpand)

        if ashrink is None:
            if not hasattr(cls, "ashrink") and scope == PortScope.GLOBAL:
                raise StandardHookError(
                    f"You need to pass 'ashrink' method or {cls} needs to implement a"
                    " ashrink method if it wants to become a GLOBAL structure"
                )
            ashrink = getattr(cls, "ashrink", shelve_ashrink)

        if acollect is None:
            if scope == PortScope.GLOBAL:
                acollect = void_acollect
            else:
                acollect = getattr(cls, "acollect", shelve_acollect)

        if predicate is None:
            predicate = build_instance_predicate(cls)

        if identifier is None:
            if not hasattr(cls, "get_identifier"):
                raise StandardHookError(
                    f"You need to pass 'identifier' or  {cls} needs to implement a"
                    " get_identifier method"
                )
            identifier = cls.get_identifier()

        return FullFilledStructure(
            fullfilled_by="StandardHook",
            cls=cls,
            identifier=identifier,
            scope=scope,
            aexpand=aexpand,
            ashrink=ashrink,
            acollect=acollect,
            predicate=predicate,
            convert_default=convert_default,
            default_widget=default_widget,
            default_returnwidget=default_returnwidget,
        )
