"""Types for the structures module."""

from typing import Protocol, Optional, List, Union
from rekuest_next.api.schema import (
    AssignWidgetInput,
    ChoiceInput,
    ReturnWidgetInput,
    PortKind,
)
from pydantic import BaseModel, ConfigDict, model_validator, ValidationInfo
from typing import (
    Any,
    Awaitable,
    Callable,
    Type,
    runtime_checkable,
)

JSONSerializable = Union[str, int, float, bool, None, dict, list]


@runtime_checkable
class Shrinker(Protocol):
    """A callable that takes a value and returns a string representation of it that
    can be serialized to json."""

    def __call__(self, value: Any) -> Awaitable[str]:  # noqa: ANN401
        """Convert a value to a string representation."""

        ...


@runtime_checkable
class Predicator(Protocol):
    """A callable that takes a value and returns True if the value is of the
    correct type for the structure."""

    def __call__(self, value: Any) -> bool:  # noqa: ANN401
        """Check if the value is of the correct type for the structure."""

        ...


@runtime_checkable
class DefaultConverter(Protocol):
    """A callable that takes a value and returns a string representation of it
    that can be serialized to json."""

    def __call__(self, value: Any) -> str:  # noqa: ANN401
        """Convert a value to a string representation."""
        ...


@runtime_checkable
class Expander(Protocol):
    """A callable that takes a string and returns the original value,
    which can be deserialized from json."""

    def __call__(self, value: str) -> Awaitable[Any]:
        """Convert a string representation back to the original value."""

        ...


class FullFilledStructure(BaseModel):
    """A structure that can be registered to the structure registry
    and containts all the information needed to serialize and deserialize
    the structure. If dealing with a structure that is cglobal, aexpand and
    ashrink need to be passed. If dealing with a structure that is local,
    aexpand and ashrink can be None.
    """

    cls: Type
    identifier: str
    aexpand: Expander | None
    ashrink: Shrinker | None
    description: Optional[str]
    predicate: Callable[[Any], bool]
    convert_default: Callable[[Any], str] | None
    default_widget: Optional[AssignWidgetInput]
    default_returnwidget: Optional[ReturnWidgetInput]
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    @model_validator(mode="after")
    def validate_cls(
        cls, value: "FullFilledType", info: ValidationInfo
    ) -> "FullFilledType":
        """Validate the class to make sure it has the required methods if it is a global structure."""
        if value.aexpand is None and value.kind == PortKind.STRUCTURE:
            raise ValueError(
                f"You need to pass 'expand' method or {cls.cls} needs to implement a"
                " aexpand method if it wants to become a structure"
            )
        if value.ashrink is None and value.kind == PortKind.STRUCTURE:
            raise ValueError(
                f"You need to pass 'ashrink' method or {cls.cls} needs to implement a"
                " ashrink method if it wants to become a GLOBAL structure"
            )

        return value


class FullFilledEnum(BaseModel):
    """A fullfiled enum that can be used to serialize and deserialize"""

    cls: Type
    identifier: str
    description: Optional[str]
    choices: List[ChoiceInput]
    predicate: Predicator
    convert_default: DefaultConverter | None
    default_widget: Optional[AssignWidgetInput]
    default_returnwidget: Optional[ReturnWidgetInput]
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")


class FullFilledMemoryStructure(BaseModel):
    """A fullfiled memory structure that can be used to serialize and deserialize"""

    cls: Type
    identifier: str
    predicate: Predicator
    description: Optional[str]
    convert_default: DefaultConverter | None
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")


class FullFilledModel(BaseModel):
    """A fullfiled model that can be used to serialize and deserialize"""

    cls: Type
    identifier: str
    predicate: Predicator
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")


FullFilledType = Union[
    FullFilledStructure, FullFilledEnum, FullFilledMemoryStructure, FullFilledModel
]
