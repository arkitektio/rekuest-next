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
from .errors import HookError


async def id_shrink(self):
    return self.id


def identity_default_converter(x):
    return x


def cls_to_identifier(cls: Type) -> Identifier:
    try:
        return f"{cls.__module__.lower()}.{cls.__name__.lower()}"
    except AttributeError:
        raise HookError(
            f"Cannot convert {cls} to identifier. The class needs to have a __module__ and __name__ attribute."
        )


def build_instance_predicate(cls: Type):
    return lambda x: isinstance(x, cls)


class StandardHookError(HookError):
    pass


class GlobalStructureHook(BaseModel):
    """The Standard Hook is a hook that can be registered to the structure registry.

    It will register all local structures in a shelve and will use the shelve to
    expand and shrink the structures. All global structures will net to defined aexpand and
    ashrink using the methods defined in the structure.

    """

    def is_applicable(self, cls: Type) -> bool:
        """Given a class, return True if this hook is applicable to it"""
        if not hasattr(cls, "aexpand"):
            return False

        if not hasattr(cls, "ashrink") and not hasattr(cls, "id"):
            return False

        if not hasattr(cls, "get_identifier"):
            return False

        return True  # Catch all

    def apply(
        self,
        cls: Type,
    ) -> FullFilledStructure:
        if hasattr(cls, "get_identifier"):
            identifier = cls.get_identifier()
        else:
            identifier = self.cls_to_identifier(cls)

        if hasattr(cls, "get_default_widget"):
            default_widget = cls.get_default_widget()
        else:
            default_widget = None

        if hasattr(cls, "get_default_returnwidget"):
            default_returnwidget = cls.get_default_returnwidget()
        else:
            default_returnwidget = None

        if hasattr(cls, "convert_default"):
            convert_default = cls.convert_default

        convert_default = identity_default_converter

        aexpand = getattr(cls, "aexpand")

        if not hasattr(cls, "ashrink"):
            raise StandardHookError(
                f"You need to pass 'ashrink' method or {cls} needs to implement a"
                " ashrink method if it wants to become a GLOBAL structure"
            )

        ashrink = getattr(cls, "ashrink", id_shrink)

        if hasattr(cls, "predicate"):
            predicate = getattr(cls, "predicate")
        else:
            predicate = build_instance_predicate(cls)

        return FullFilledStructure(
            cls=cls,
            identifier=identifier,
            scope=PortScope.GLOBAL,
            aexpand=aexpand,
            ashrink=ashrink,
            predicate=predicate,
            convert_default=convert_default,
            default_widget=default_widget,
            default_returnwidget=default_returnwidget,
        )
