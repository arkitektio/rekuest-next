from dataclasses import dataclass
from fieldz import fields, Field
from typing import List, Dict
from .types import FullFilledArg
import inflection


def model(cls):
    """Mark a class as a model. This is used to
    identify the model in the rekuest_next system."""

    try:
        fields(cls)
    except TypeError:
        raise TypeError(
            "Models must be serializable by fieldz in order to be used in rekuest_next."
        )

    setattr(cls, "__rekuest_model__", inflection.underscore(cls.__name__))

    return dataclass(cls)


def is_model(cls):
    """Check if a class is a model."""

    return getattr(cls, "__rekuest_model__", False)


def get_model_name(cls):
    return getattr(cls, "__rekuest_model__")


def retrieve_args_for_model(cls) -> List[FullFilledArg]:
    children_clses = fields(cls)

    args = []
    for field in children_clses:
        print(field.default)
        print(field)
        args.append(
            FullFilledArg(
                cls=field.type,
                default=field.default if field.default != Field.MISSING else None,
                key=field.name,
            )
        )

    return args
