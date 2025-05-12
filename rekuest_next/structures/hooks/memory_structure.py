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


def cls_to_identifier(cls: Type[object]) -> Identifier:
    """Convert a class to an identifier."""
    try:
        return Identifier.validate(f"{cls.__module__.lower()}.{cls.__name__.lower()}")
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

    cls_to_identifier: Callable[[Type[object]], Identifier] = cls_to_identifier

    def is_applicable(self, cls: Type[object]) -> bool:
        """Given a class, return True if this hook is applicable to it"""
        # everything is applicable
        return True  # Catch all

    def apply(
        self,
        cls: Type[object],
    ) -> FullFilledMemoryStructure:
        """Apply the hook to the class and return a FullFilledStructure."""
        if hasattr(cls, "get_identifier"):
            identifier = cls.get_identifier()  # type: ignore
        else:
            identifier = self.cls_to_identifier(cls)

        predicate = build_instance_predicate(cls)

        return FullFilledMemoryStructure(
            cls=cls,
            identifier=identifier,  # type: ignore
            predicate=predicate,
            description=None,
        )
