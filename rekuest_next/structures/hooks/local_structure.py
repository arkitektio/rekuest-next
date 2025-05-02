from typing import (
    Callable,
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


class LocalStructureHook(BaseModel):
    cls_to_identifier: Callable[[Type], Identifier] = cls_to_identifier
    """The Standard Hook is a hook that can be registered to the structure registry.

    It will register all local structures in a shelve and will use the shelve to
    expand and shrink the structures. All global structures will net to defined aexpand and
    ashrink using the methods defined in the structure.

    """

    def is_applicable(self, cls: Type) -> bool:
        """Given a class, return True if this hook is applicable to it"""
        # everything is applicable
        return True  # Catch all

    def apply(
        self,
        cls: Type,
    ) -> FullFilledStructure:
        if hasattr(cls, "get_identifier"):
            identifier = cls.get_identifier()
        else:
            identifier = self.cls_to_identifier(cls)

        predicate = build_instance_predicate(cls)

        return FullFilledStructure(
            cls=cls,
            identifier=identifier,
            scope=PortScope.LOCAL,
            aexpand=None,
            ashrink=None,
            predicate=predicate,
            convert_default=identity_default_converter,
            default_widget=None,
            default_returnwidget=None,
        )
