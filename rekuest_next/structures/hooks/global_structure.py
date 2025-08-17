"""Global Structure Hook"""

from typing import (
    Protocol,
    Type,
)
from pydantic import BaseModel
from rekuest_next.scalars import Identifier
from rekuest_next.structures.types import FullFilledStructure
from rekuest_next.structures.utils import build_instance_predicate, id_shrink
from .errors import HookError


def identity_default_converter(x: str) -> str:
    """Convert a value to its string representation."""
    return x


class GlobalStructureHookError(HookError):
    """Base class for all standard hook errors."""

    pass


class Identifiable(Protocol):
    """A protocol for objects that can be identified as a global structure."""

    @classmethod
    def get_identifier(cls) -> Identifier:
        """Get the identifier of the object."""
        ...

    @classmethod
    async def aexpand(cls, value: object) -> "Identifiable":
        """Expand the value to its string representation."""
        ...


class GlobalStructureHook(BaseModel):
    """The Standard Hook is a hook that can be registered to the structure registry.

    It will register all local structures in a shelve and will use the shelve to
    expand and shrink the structures. All global structures will net to defined aexpand and
    ashrink using the methods defined in the structure.

    """

    def is_applicable(self, cls: Type[object]) -> bool:
        """Given a class, return True if this hook is applicable to it"""
        if not hasattr(cls, "aexpand"):
            return False

        if not hasattr(cls, "ashrink"):
            return False

        if not hasattr(cls, "get_identifier"):
            return False

        return True  # Catch all

    def apply(
        self,
        cls: Type[object],
    ) -> FullFilledStructure:
        """Apply the hook to the class and return a FullFilledStructure."""

        if hasattr(cls, "get_identifier"):
            identifier: Identifier = cls.get_identifier()  # type: ignore
        else:
            raise GlobalStructureHookError(
                f"Class {cls} does not have a get_identifier method"
            )

        if hasattr(cls, "get_default_widget"):
            default_widget = cls.get_default_widget()  # type: ignore
        else:
            default_widget = None

        if hasattr(cls, "get_default_returnwidget"):
            default_returnwidget = cls.get_default_returnwidget()  # type: ignore
        else:
            default_returnwidget = None

        if hasattr(cls, "convert_default"):
            convert_default = cls.convert_default  # type: ignore

        convert_default = identity_default_converter

        aexpand = getattr(cls, "aexpand")

        if not hasattr(cls, "ashrink"):
            raise GlobalStructureHookError(
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
            identifier=identifier,  # type: ignore
            aexpand=aexpand,
            ashrink=ashrink,
            predicate=predicate,
            description=None,
            convert_default=convert_default,
            default_widget=default_widget,  # type: ignore
            default_returnwidget=default_returnwidget,  # type: ignore
        )
