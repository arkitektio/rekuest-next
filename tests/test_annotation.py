from enum import Enum
import pytest
from rekuest_next.definition.define import prepare_definition
from rekuest_next.api.schema import ChoiceInput, ValidatorInput, EffectInput, EffectKind
from rekuest_next.widgets import ChoiceWidget
from typing import Annotated


class Service(str, Enum):
    KABINET = "Kabinet"
    ELEKTRO = "Elektro"


@pytest.mark.define
def test_annotation_good(simple_registry):
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
        ValidatorInput(
            function="(services) => services.length > 0",
            errorMessage="You must select at least one service to install",
            dependencies=[],
        ),
    ]

    def func(services: Services) -> str:
        return services

    functional_definition = prepare_definition(func, structure_registry=simple_registry)

    assert functional_definition.args[0].assign_widget.choices[0].value == Service.KABINET
    assert functional_definition.args[0].assign_widget.choices[1].value == Service.ELEKTRO
    assert (
        functional_definition.args[0].validators[0].function == "(services) => services.length > 0"
    )


@pytest.mark.define
def test_validator_func():
    ValidatorInput(
        function="(services) => services.length > 0",
        errorMessage="You must select at least one service to install",
        dependencies=[],
    )


@pytest.mark.define
def test_validator_func():
    with pytest.raises(ValueError):
        ValidatorInput(
            function="(services, x) => services.length > 0",
            errorMessage="You must select at least one service to install",
            dependencies=[],
        )

    with pytest.raises(ValueError):
        ValidatorInput(
            function="(services) => services.length > 0",
            errorMessage="You must select at least one service to install",
            dependencies=["services"],
        )


@pytest.mark.define
def test_validator_should_alert_if_not_in_keys(simple_registry):
    TheStr = Annotated[
        str,
        ValidatorInput(
            function="(services, other_key) => services.length > 0",
            errorMessage="You must select at least one service to install",
            dependencies=["other_key"],
        ),
    ]

    def func(name: TheStr) -> str:
        return name

    with pytest.raises(ValueError):
        functional_definition = prepare_definition(func, structure_registry=simple_registry)


@pytest.mark.define
def test_effect_integration(simple_registry):
    TheStr = Annotated[
        str,
        EffectInput(
            kind=EffectKind.HIDE,
            function="(services, other_key) => other_key > 0",
            dependencies=["other_key"],
        ),
    ]

    def func(name: TheStr, other_key: bool) -> str:
        return name

    functional_definition = prepare_definition(func, structure_registry=simple_registry)
