"""This module contains the model decorator that can
be used to mark a class as a model."""

from dataclasses import dataclass
from fieldz import fields, Field  # type: ignore
from typing import Any, List, Optional, Type, TypeVar
import inflection
from pydantic import BaseModel


T = TypeVar("T", bound=Type[Any])


def model(cls: T) -> T:
    """Mark a class as a model. This is used to
    identify the model in the rekuest_next system."""

    try:
        fields(cls)
    except TypeError:
        try:
            return model(dataclass(cls))  # type: ignore
        except TypeError:
            raise TypeError(
                "Models must be serializable by fieldz in order to be used in rekuest_next."
            )

    setattr(cls, "__rekuest_model__", inflection.underscore(cls.__name__))

    return cls


def is_model(cls: Type[Any]) -> bool:
    """Check if a class is a model."""

    return getattr(cls, "__rekuest_model__", False)


class InspectedModel(BaseModel):
    """A model that can be used to serialize and deserialize"""

    identifier: str
    description: Optional[str]
    args: List["InspectedArg"]


class InspectedArg(BaseModel):
    """A fullfiled argument of a model that can be used to serialize and deserialize"""

    key: str
    default: Optional[Any]
    cls: Any
    description: Optional[str]


def inspect_args_for_model(cls: Type[Any]) -> List[InspectedArg]:
    """Retrieve the arguments for a model."""
    children_classes: tuple[Field[Any], ...] = fields(cls)  # type: ignore

    args: list[InspectedArg] = []
    for field in children_classes:
        args.append(
            InspectedArg(
                cls=field.annotated_type or field.type,
                default=field.default if field.default != Field.MISSING else None,
                key=field.name,
                description=field.description,
            )
        )
    return args


def inspect_model_class(cls: Type[Any]) -> InspectedModel:
    """Retrieve the fullfilled model for a class."""
    return InspectedModel(
        identifier=cls.__rekuest_model__,
        description=cls.__doc__,
        args=inspect_args_for_model(cls),
    )
