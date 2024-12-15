from typing import Protocol, Optional, List
from rekuest_next.api.schema import (
    AssignWidgetInput,
    ReturnWidgetInput,
    PortInput,
    PortScope,
)
from pydantic import BaseModel, ConfigDict
from typing import (
    Any,
    Awaitable,
    Callable,
    Type,
)


class PortBuilder(Protocol):
    def __call__(
        self,
        cls: type,
        assign_widget: Optional[AssignWidgetInput],
        return_widget: Optional[ReturnWidgetInput],
    ) -> PortInput: ...


class FullFilledStructure(BaseModel):
    fullfilled_by: str
    cls: Type
    identifier: str
    scope: PortScope
    aexpand: Callable[
        [
            str,
        ],
        Awaitable[Any],
    ]
    ashrink: Callable[
        [
            any,
        ],
        Awaitable[str],
    ]
    acollect: Callable[
        [
            str,
        ],
        Awaitable[Any],
    ]
    predicate: Callable[[Any], bool]
    convert_default: Callable[[Any], str]
    default_widget: Optional[AssignWidgetInput]
    default_returnwidget: Optional[ReturnWidgetInput]
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")



class FullFilledArg(BaseModel):
    key: str
    default: Optional[Any]
    cls: Any
    description: Optional[str]


class FullFilledModel(BaseModel):
    identifier: str
    description: Optional[str]
    args: List[FullFilledArg]
