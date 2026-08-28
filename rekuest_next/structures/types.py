"""Types for the structures module."""

from enum import Enum
from typing import Protocol
from rath.scalars import ID
from rekuest_next.api.schema import (
    AssignWidgetInput,
    ChoiceInput,
    ReturnWidgetInput,
)
from pydantic import BaseModel, ConfigDict, Field
from typing import (
    Any,
    runtime_checkable,
)
from collections.abc import Awaitable, Callable


JSONSerializable = (
    str | int | float | bool | None | dict[str, "JSONSerializable"] | list["JSONSerializable"]
)


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

    cls: type[object]
    identifier: str
    aexpand: Expander
    ashrink: Shrinker
    description: str | None
    predicate: Callable[[Any], bool]
    convert_default: Callable[[Any], str] | None
    default_widget: AssignWidgetInput | None
    default_returnwidget: ReturnWidgetInput | None
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")


class FullFilledEnum(BaseModel):
    """A fullfiled enum that can be used to serialize and deserialize"""

    cls: type[Enum]
    identifier: str
    description: str | None
    choices: list[ChoiceInput]
    predicate: Predicator
    convert_default: Callable[[Any], str]
    default_widget: AssignWidgetInput | None
    default_returnwidget: ReturnWidgetInput | None
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")


class FullFilledMemoryStructure(BaseModel):
    """A fullfiled memory structure that can be used to serialize and deserialize"""

    cls: Any
    identifier: str
    predicate: Predicator
    description: str | None
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")


class FullFilledModel(BaseModel):
    """A fullfiled model that can be used to serialize and deserialize"""

    cls: type[Expandable]
    identifier: str
    predicate: Predicator
    description: str | None = Field(default=None)
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")


FullFilledType = (
    FullFilledStructure | FullFilledEnum | FullFilledMemoryStructure | FullFilledModel
)
