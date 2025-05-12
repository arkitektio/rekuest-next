"""Traits for ports and widgets, especially for validating the input"""

from typing import TYPE_CHECKING, Any
from pydantic import BaseModel, field_validator, model_validator
import re

from rekuest_next.messages import JSONSerializable

if TYPE_CHECKING:
    from rekuest_next.api.schema import (
        PortInput,
        DefinitionInput,
        ValidatorInput,
        ReturnWidgetInput,
        AssignWidgetInput,
    )


class PortTrait(BaseModel):
    """
    Class for validating port input
    on the client side

    """

    @field_validator("default", check_fields=False)
    def default_validator(cls, v: Any) -> JSONSerializable:  # noqa: ANN401
        """Validate the default value of the port"""
        # Check if the default value is JSON serializable
        if v is None:
            return v

        if not isinstance(v, (str, int, float, dict, list, bool)):
            raise ValueError(
                "Default value must be JSON serializable, got: " + str(v)
            ) from None

        return v  # type: ignore[return-value]

    @model_validator(mode="after")  # type: ignore[override]
    def validate_portkind_nested(cls, self: "PortInput") -> "PortInput":
        """Validate the function of the validator"""
        from rekuest_next.api.schema import PortKind

        if self.kind == PortKind.STRUCTURE:
            if self.identifier is None:
                raise ValueError(
                    "When specifying a structure you need to provide an arkitekt identifier got:"
                )

        if self.kind == PortKind.LIST:
            if self.children is None:
                raise ValueError(
                    "When specifying a list you need to provide a wrapped 'children' port"
                )
            assert len(self.children) == 1, "List can only have one child"

        if self.kind == PortKind.DICT:
            if self.children is None:
                raise ValueError(
                    "When specifying a dict you need to provide a wrapped 'children' port"
                )
            assert len(self.children) == 1, (
                "Dict can only one child (key is always strings)"
            )

        return self


class WidgetInputTrait(BaseModel):
    """
    Class for validating widget input
    on the client side

    """

    @model_validator(mode="after")  # type: ignore[override]
    def validate_widgetkind_nested(
        cls, self: "AssignWidgetInput"
    ) -> "AssignWidgetInput":
        """Validate the function of the validator"""
        from rekuest_next.api.schema import AssignWidgetKind

        if self.kind == AssignWidgetKind.SEARCH:
            if self.query is None:
                raise ValueError(
                    "When specifying a SearchWidget you need to provide an query parameter"
                )

        if self.kind == AssignWidgetKind.SLIDER:
            if self.min is None or self.max is None:
                raise ValueError(
                    "When specifying a Slider you need to provide an 'max and 'min' parameter"
                )

            if self.min > self.max:
                raise ValueError(
                    "When specifying a Slider you need to provide an 'max' greater than 'min'"
                )

        return self


class ReturnWidgetInputTrait(BaseModel):
    """
    Class for validating widget input
    on the client side

    """

    @model_validator(mode="after")  # type: ignore[override]
    def validate_widgetkind_nested(
        cls, self: "ReturnWidgetInput"
    ) -> "ReturnWidgetInput":
        """Validate the function of the validator"""
        from rekuest_next.api.schema import ReturnWidgetKind

        if self.kind == ReturnWidgetKind.CUSTOM:
            if self.hook is None:
                raise ValueError(
                    "When specifying a CustomReturnWidget you need to provide a 'hook'"
                    " parameter, corresponding to the desired reigstered hook"
                )

        return self


class ValidatorInputTrait(BaseModel):
    """An addin trait for validating the input of a validator"""

    @model_validator(mode="after")  # type: ignore[override]
    def validate_widgetkind_nested(cls, self: "ValidatorInput") -> "ValidatorInput":
        """Validate the function of the validator"""
        args_match = re.match(r"\((.*?)\)", self.function)
        if args_match:
            args = [
                arg.strip() for arg in args_match.group(1).split(",") if arg.strip()
            ]
            if not args:
                raise ValueError("Function must have at least one argument")

            dependencies = self.dependencies or []

            if len(args) - 1 is not len(dependencies):
                raise ValueError(
                    f"The number of arguments in the function must match the number of dependencies, plus one for the input value. Found {len(args)} arguments and {len(dependencies)} dependencies"
                )
        else:
            raise ValueError("Function must have at least one argument")

        return self


class DefinitionInputTrait(BaseModel):
    """An addin trait for validating the input of a definition"""

    @model_validator(mode="after")  # type: ignore[override]
    def validate_validators(cls, self: "DefinitionInput") -> "DefinitionInput":
        """Validate the ports"""
        all_arg_keys: list[str] = []

        for port in self.args:
            all_arg_keys.append(port.key)

        for port in self.args:
            if port.validators:
                for validator in port.validators:
                    if validator.dependencies:
                        for dep in validator.dependencies:
                            if dep not in all_arg_keys:
                                raise ValueError(
                                    f"Dependency '{dep}' for '{validator.function}' at port '{port.key} not found in args. Please make sure the dependency is in the args"
                                )

        return self
