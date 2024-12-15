from dataclasses import dataclass
from fieldz import fields, Field
from typing import List
from .types import FullFilledArg, FullFilledModel
import inflection


def model(cls):
    """Mark a class as a model. This is used to
    identify the model in the rekuest_next system."""

    try:
        fields(cls)
    except TypeError:
        try:
            return model(dataclass(cls))
        except TypeError:
            raise TypeError(
                "Models must be serializable by fieldz in order to be used in rekuest_next."
            )

    setattr(cls, "__rekuest_model__", inflection.underscore(cls.__name__))

    return cls


def is_model(cls):
    """Check if a class is a model."""

    return getattr(cls, "__rekuest_model__", False)


def retrieve_args_for_model(cls) -> List[FullFilledArg]:
    children_clses = fields(cls)

    args = []
    for field in children_clses:
        args.append(
            FullFilledArg(
                cls=field.type,
                default=field.default if field.default != Field.MISSING else None,
                key=field.name,
                description=field.description,
            )
        )
    return args


def retrieve_fullfiled_model(cls) -> FullFilledModel:
    return FullFilledModel(
        identifier=cls.__rekuest_model__,
        description=cls.__doc__,
        args=retrieve_args_for_model(cls),
    )
