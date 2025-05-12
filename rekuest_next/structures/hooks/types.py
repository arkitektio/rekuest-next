""" "General types for Hooks in Rekuest Next"""

from typing import (
    Type,
    Protocol,
    runtime_checkable,
)
from rekuest_next.structures.types import FullFilledType


@runtime_checkable
class RegistryHook(Protocol):
    """A hook that can be registered to the structure registry
    and will be called when a structure is about to be registered
    and can be used to modify the structure with the registry

    """

    def is_applicable(
        self,
        cls: Type[object],
    ) -> bool:
        """Given a class, return True if this hook is applicable to it"""
        ...

    def apply(
        self,
        cls: Type[object],
    ) -> FullFilledType:
        """App a class, return True if this hook is applicable to it"""
        ...
