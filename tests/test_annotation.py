"""Test annotation for rekuest_next library."""

from enum import Enum
import pytest
from rekuest_next.definition.define import prepare_definition
from rekuest_next.api.schema import (
    ActionArgumentInput,
    AgentProbeInput,
    ChoiceInput,
    UtilCallInput,
    ValidatorInput,
    EffectKind,
)
from rekuest_next.blok.parser import parse_util_call
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.widgets import ChoiceWidget, withEffect, withValidator
from typing import Annotated


class Service(str, Enum):
    """Enum for services."""

    KABINET = "Kabinet"
    ELEKTRO = "Elektro"


@pytest.mark.define
def test_annotation_good(simple_registry: StructureRegistry) -> None:
    """Test if the annotation is correctly integrated in the definition."""
    Services = Annotated[
        list[str],
        ChoiceWidget(
            choices=[
                ChoiceInput(
                    value=Service.KABINET,
                    description="Would you like to install Kabinet?",
                    image="https://www.google.com",
                    label="Install Kabinet",
                ),
                ChoiceInput(
                    value=Service.ELEKTRO,
                    description="Would you like to install Kabinet?",
                    image="https://www.google.com",
                    label="Install Kabinet",
                ),
            ]
        ),
        withValidator(
            "gt(value, 0)",
            error_message="You must select at least one service to install",
        ),
    ]

    def func(services: Services) -> str:  # type: ignore
        return services

    functional_definition = prepare_definition(func, structure_registry=simple_registry)

    port = functional_definition.args[0]
    assert port.widget is not None, "Widget should be attached to the argument"
    assert port.widget.kind == "CHOICE"
    assert port.choices is not None, "The widget's choices are promoted onto the port"
    assert port.choices[0].value == Service.KABINET
    assert port.choices[1].value == Service.ELEKTRO
    assert "choices" not in port.widget.model_dump(by_alias=True)

    validators = functional_definition.args[0].validators
    assert validators is not None
    assert validators[0].call.operation == "gt"
    assert validators[0].call.arguments is not None
    assert validators[0].call.arguments[0].key == "a"
    assert validators[0].call.arguments[0].value_path == "value"
    assert validators[0].call.arguments[1].value_literal == 0
    assert validators[0].error_message == "You must select at least one service to install"


@pytest.mark.define
def test_validator_func() -> None:
    """A validator that only references its own value needs no dependencies."""
    validator = ValidatorInput(
        call=parse_util_call("gt(value, 3)"),
        error_message="Must be greater than 3",
    )
    assert validator.dependencies is None
    assert validator.call.operation == "gt"


@pytest.mark.define
def test_validator_func_wrong_deps() -> None:
    """Impure or undeclared calls are rejected before upload."""
    with pytest.raises(ValueError, match="'other' via value_path"):
        ValidatorInput(
            call=parse_util_call("gt(value, other.min)"),
            error_message="Must exceed the minimum",
            dependencies=[],
        )

    with pytest.raises(ValueError, match="must name an operation"):
        ValidatorInput(call=UtilCallInput(operation="", arguments=None))

    with pytest.raises(ValueError, match="must be pure"):
        ValidatorInput(
            call=UtilCallInput(
                operation="gt",
                arguments=(
                    ActionArgumentInput(
                        key="a",
                        value_list=(
                            ActionArgumentInput(
                                agent_call=AgentProbeInput(
                                    dependency="stage", operation="move"
                                )
                            ),
                        )
                    ),
                ),
            ),
        )


@pytest.mark.define
def test_validator_should_alert_if_not_in_keys(
    simple_registry: StructureRegistry,
) -> None:
    """Test if value errors are raised when the dependences are not in the definition"""
    TheStr = Annotated[
        str,
        withValidator(
            "gt(value, other_key)",
            error_message="You must select at least one service to install",
        ),
    ]

    def func(name: TheStr) -> str:  # type: ignore
        return name

    with pytest.raises(ValueError, match="invalid dependency: other_key"):
        prepare_definition(func, structure_registry=simple_registry)


@pytest.mark.define
def test_effect_integration(simple_registry: StructureRegistry) -> None:
    """Test if the effect is correctly integrated in the definition."""
    TheStr = Annotated[
        str,
        withEffect(EffectKind.HIDE, "gt(other_key, 0)"),
    ]

    def func(name: TheStr, other_key: bool) -> str:  # type: ignore
        return name

    definition = prepare_definition(func, structure_registry=simple_registry)

    effects = definition.args[0].effects
    assert effects is not None
    assert effects[0].kind == EffectKind.HIDE
    assert effects[0].dependencies == ("other_key",)
    assert effects[0].call.operation == "gt"
    assert effects[0].call.arguments is not None
    assert effects[0].call.arguments[0].value_path == "other_key"
