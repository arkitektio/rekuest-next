"""Types for the structures module."""

from enum import Enum
from typing import Protocol, Optional, List, Union
from rath.scalars import ID
from rekuest_next.api.schema import (
    AssignWidgetInput,
    ChoiceInput,
    ReturnWidgetInput,
)
from pydantic import BaseModel, ConfigDict, Field
from typing import (
    Any,
    Awaitable,
    Callable,
    Type,
    runtime_checkable,
)


JSONSerializable = Union[
    str, int, float, bool, None, dict[str, "JSONSerializable"], list["JSONSerializable"]
]


@runtime_checkable
class Expandable(Protocol):
    """A callable that takes a set of keyword arguments to initialize the object."""

    def __init__(self, value: Any) -> None:  # noqa: ANN401
        """Initialize the Expandable with the value."""
        ...


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

    def __call__(self, id: ID) -> Awaitable[Any]:
        """Convert a string representation back to the original value."""

        ...


class FullFilledStructure(BaseModel):
    """A structure that can be registered to the structure registry
    and containts all the information needed to serialize and deserialize
    the structure. If dealing with a structure that is cglobal, aexpand and
    ashrink need to be passed. If dealing with a structure that is local,
    aexpand and ashrink can be None.
    """

    cls: Type[object]
    identifier: str
    aexpand: Expander
    ashrink: Shrinker
    description: Optional[str]
    predicate: Callable[[Any], bool]
    convert_default: Callable[[Any], str] | None
    default_widget: Optional[AssignWidgetInput]
    default_returnwidget: Optional[ReturnWidgetInput]
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")


class FullFilledEnum(BaseModel):
    """A fullfiled enum that can be used to serialize and deserialize"""

    cls: Type[Enum]
    identifier: str
    description: Optional[str]
    choices: List[ChoiceInput]
    predicate: Predicator
    convert_default: Callable[[Any], str]
    default_widget: Optional[AssignWidgetInput]
    default_returnwidget: Optional[ReturnWidgetInput]
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")


class FullFilledMemoryStructure(BaseModel):
    """A fullfiled memory structure that can be used to serialize and deserialize"""

    cls: Any
    identifier: str
    predicate: Predicator
    description: Optional[str]
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")


class FullFilledModel(BaseModel):
    """A fullfiled model that can be used to serialize and deserialize"""

    cls: Type[Expandable]
    identifier: str
    predicate: Predicator
    description: Optional[str] = Field(default=None)
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")


FullFilledType = Union[
    FullFilledStructure, FullFilledEnum, FullFilledMemoryStructure, FullFilledModel
]
