from typing import Protocol, Optional, List
from rekuest_next.api.schema import (
    AssignWidgetInput,
    ReturnWidgetInput,
    PortInput,
    PortScope,
)
from pydantic import BaseModel, ConfigDict, model_validator
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
    cls: Type
    identifier: str
    scope: PortScope
    aexpand: (
        Callable[
            [
                str,
            ],
            Awaitable[Any],
        ]
        | None
    )
    ashrink: (
        Callable[
            [
                any,
            ],
            Awaitable[str],
        ]
        | None
    )
    predicate: Callable[[Any], bool]
    convert_default: Callable[[Any], str] | None
    default_widget: Optional[AssignWidgetInput]
    default_returnwidget: Optional[ReturnWidgetInput]
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    @model_validator(mode="after")
    def validate_cls(cls, value, info) -> "FullFilledStructure":
        if value.aexpand is None and value.scope == PortScope.GLOBAL:
            raise ValueError(
                f"You need to pass 'expand' method or {cls.cls} needs to implement a"
                " aexpand method if it wants to become a GLOBAL structure"
            )
        if value.ashrink is None and value.scope == PortScope.GLOBAL:
            raise ValueError(
                f"You need to pass 'ashrink' method or {cls.cls} needs to implement a"
                " ashrink method if it wants to become a GLOBAL structure"
            )

        return value


class FullFilledArg(BaseModel):
    key: str
    default: Optional[Any]
    cls: Any
    description: Optional[str]


class FullFilledModel(BaseModel):
    identifier: str
    description: Optional[str]
    args: List[FullFilledArg]
