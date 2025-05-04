"""Local Structure Hook"""

from typing import (
    Callable,
    Type,
)
from pydantic import BaseModel
from rekuest_next.structures.types import FullFilledMemoryStructure
from rekuest_next.api.schema import (
    Identifier,
)
from rekuest_next.structures.utils import build_instance_predicate
from .errors import HookError


async def id_shrink(self: BaseModel) -> str:
    """Convert a structure with an id to a string representation by using the id."""
    return self.id


def identity_default_converter(x: str) -> str:
    """Convert a value to its string representation."""
    return x


def cls_to_identifier(cls: Type) -> Identifier:
    """Convert a class to an identifier."""
    try:
        return f"{cls.__module__.lower()}.{cls.__name__.lower()}"
    except AttributeError:
        raise HookError(
            f"Cannot convert {cls} to identifier. The class needs to have a __module__ and __name__ attribute."
        )


class LocalStructureHookError(HookError):
    """Base class for all local structure hook errors."""

    pass


class MemoryStructureHook(BaseModel):
    """The Local Memotry Strucute Hook is a hook that can be registered to the structure registry.

    It will register all types as memory structures (that will be put into a local shelve
    instread of shrinking and expanding them) .

    """

    cls_to_identifier: Callable[[Type], Identifier] = cls_to_identifier

    def is_applicable(self, cls: Type) -> bool:
        """Given a class, return True if this hook is applicable to it"""
        # everything is applicable
        return True  # Catch all

    def apply(
        self,
        cls: Type,
    ) -> FullFilledMemoryStructure:
        """Apply the hook to the class and return a FullFilledStructure."""
        if hasattr(cls, "get_identifier"):
            identifier = cls.get_identifier()
        else:
            identifier = self.cls_to_identifier(cls)

        predicate = build_instance_predicate(cls)

        return FullFilledMemoryStructure(
            cls=cls,
            identifier=identifier,
            predicate=predicate,
            description=None,
            convert_default=identity_default_converter,
        )
