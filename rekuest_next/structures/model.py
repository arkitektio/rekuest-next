"""This module contains the model decorator that can
be used to mark a class as a model."""

import inspect
import re
import sys
from dataclasses import dataclass, field
from typing import Any, List, Optional, Type, TypeVar, TYPE_CHECKING
import inflection
from fieldz import fields, Field  # type: ignore
from pydantic import BaseModel

from rekuest_next.api.schema import ValidatorInput
from rekuest_next.scalars import ValidatorFunction  # type: ignore

# Handle Python version compatibility for dataclass_transform
if sys.version_info >= (3, 11):
    from typing import dataclass_transform
else:
    from typing_extensions import dataclass_transform

T = TypeVar("T", bound=Type[Any])


def model_field(
    *args: Any,
    description: Optional[str] = None,
    validators: Optional[List[ValidatorInput]] = None,
    label: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    """Define a field for a model with an optional description and default value."""

    return field(
        *args,
        metadata={"description": description, "validators": validators, "label": label},
        **kwargs,
    )  # type: ignore


@dataclass_transform(field_specifiers=(model_field,))
def model(cls: T) -> T:
    """Mark a class as a model.

    This decorator transforms the class into a dataclass if it isn't one already,
    registers it with the rekuest system, and provides detailed error messages
    if the definition fails.
    """

    try:
        # Check if it's already valid (e.g. manually decorated with @dataclass)
        fields(cls)
    except TypeError:
        try:
            # If not, attempt to transform it into a dataclass
            return model(dataclass(cls))  # type: ignore
        except Exception as e:
            # --- Enhanced Error Reporting ---
            try:
                # 1. Get source lines and file path
                lines, start_line = inspect.getsourcelines(cls)
                file_path = inspect.getfile(cls)

                # 2. Heuristic: Find the line causing the error
                error_line_no = start_line
                raw_line = lines[0]  # Default to class definition line

                # Look for field names in the error message (e.g., 't_hooks')
                match = re.search(r"'([^']*)'", str(e))
                if match:
                    field_name = match.group(1)
                    # Scan source for that field name
                    for idx, line in enumerate(lines):
                        if re.search(r"\b" + re.escape(field_name) + r"\b", line):
                            error_line_no = start_line + idx
                            raw_line = line
                            break

                # 3. Create the visual pointer (^^^^^)
                stripped_line = raw_line.lstrip()
                indentation = len(raw_line) - len(stripped_line)
                pointer = " " * indentation + "^" * len(stripped_line.strip())

                # 4. Construct the error message
                error_msg = (
                    f"Model error in '{cls.__name__}':\n"
                    f'  File "{file_path}", line {error_line_no}\n'
                    f"{raw_line.rstrip()}\n"
                    f"{pointer}\n"
                    f"TypeError: {e}\n"
                )
            except (OSError, TypeError):
                # Fallback if source is not available
                error_msg = f"Model definition error in '{cls.__name__}': {e}"

            raise TypeError(error_msg) from None

    # Register the model name
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
    label: Optional[str]
    description: Optional[str]
    validators: Optional[List[ValidatorInput]]


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
                description=field.description
                or field.metadata.get("description", None),
                validators=field.metadata.get("validators", None),
                label=field.metadata.get("label", None),
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
