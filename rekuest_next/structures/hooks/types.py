from typing import (
    Any,
    Awaitable,
    Callable,
    Optional,
    Type,
    Protocol,
    runtime_checkable,
)
from rekuest_next.structures.types import FullFilledStructure
from rekuest_next.api.schema import PortScope, AssignWidgetInput, ReturnWidgetInput


@runtime_checkable
class RegistryHook(Protocol):
    """A hook that can be registered to the structure registry
    and will be called when a structure is about to be registered
    and can be used to modify the structure with the registry

    """

    def is_applicable(
        self,
        cls: Type,
    ) -> bool:
        """Given a class, return True if this hook is applicable to it"""
        ...

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
        """App a class, return True if this hook is applicable to it"""
        ...
