"""Test the widgets for rekuest_next"""

from rekuest_next.widgets import SearchWidget, SliderWidget
from pydantic import ValidationError
import pytest


def test_search_widget_error_on_wrong_graphql() -> None:
    """Test the search widget error when the GraphQL query is wrong"""
    with pytest.raises(ValueError):
        SearchWidget(query="hallo", ward="mikro")

    with pytest.raises(ValueError):
        SearchWidget(query="query search {}", ward="mikro")

    with pytest.raises(ValueError):
        SearchWidget(query="query search($name: sss) {}", ward="mikro")

    with pytest.raises(ValueError):
        SearchWidget(
            query="query search($search: String) {lala {value: x label: y}}",
            ward="mikro",
        )

    with pytest.raises(ValueError):
        SearchWidget(
            query="query search($search: String) {options: karl {x label: y}}",
            ward="mikro",
        )


def test_search_widget() -> None:
    """Test if it correctly generates a search widget"""
    SearchWidget(
        query=(
            "query search($search: String, $values: [ID]){ options: karl { value: x label: y}} "
        ),
        ward="mikro",
    )


def test_slider_widget_error() -> None:
    """Test the slider widget error handling"""
    with pytest.raises(ValidationError):
        SliderWidget(min=1, max=0)

    with pytest.raises(ValidationError):
        SliderWidget(min=0)


def test_slider_widget() -> None:
    """Test the slider widget"""
    SliderWidget(
        min=0,
        max=100,
    )


def test_custom_widgets_render_catalog_components() -> None:
    """Custom widgets name a catalog component and carry pure props; members enforce their fields."""
    from pydantic import ValidationError

    from rekuest_next.api.schema import (
        ActionArgumentInput,
        ChoiceInput,
        ChoiceReturnWidgetInput,
        ComponentPropInput,
        CustomAssignWidgetInput,
        UtilCallInput,
    )
    from rekuest_next.widgets import CustomReturnWidget, CustomWidget, StringWidget

    widget = CustomWidget(
        "Gauge",
        props=[
            ComponentPropInput(
                key="max",
                util_call=UtilCallInput(
                    operation="gt",
                    arguments=(ActionArgumentInput(key="a", value_path="value"),),
                ),
            )
        ],
        dependencies=["other"],
        fallback=StringWidget(),
    )
    assert widget.kind == "CUSTOM"
    assert widget.component == "Gauge"
    assert widget.fallback is not None and widget.fallback.kind == "STRING"

    returned = CustomReturnWidget("Gauge")
    assert returned.kind == "CUSTOM" and returned.component == "Gauge"

    with pytest.raises(ValidationError, match="component"):
        CustomAssignWidgetInput()
    with pytest.raises(ValidationError, match="ward"):
        CustomAssignWidgetInput(component="X", ward="w")
    with pytest.raises(ValidationError, match="choices"):
        ChoiceReturnWidgetInput(choices=(ChoiceInput(value="a", label="A"),))


def test_choice_widgets_carry_choices_off_the_wire() -> None:
    """Choice widgets keep the choices for the port but never serialise them."""
    from rekuest_next.widgets import ChoiceReturnWidget, ChoiceWidget, withChoices

    widget = ChoiceWidget(["a", "b"])
    assert [c.value for c in widget.choices] == ["a", "b"]
    assert widget.model_dump(by_alias=True, exclude_none=True) == {"kind": "CHOICE"}
    assert withChoices(1, 2).choices[0].value == "1"
    assert ChoiceReturnWidget(["x"]).model_dump(by_alias=True, exclude_none=True) == {"kind": "CHOICE"}


def test_state_choice_needs_exactly_one_pointer() -> None:
    """A state choice widget is either a static pointer or a computed one."""
    from rekuest_next.api.schema import (
        ActionArgumentInput,
        StateChoiceAssignWidgetInput,
        UtilCallInput,
    )

    call = UtilCallInput(
        operation="sel", arguments=(ActionArgumentInput(key="a", value_path="value"),)
    )
    StateChoiceAssignWidgetInput(state_path="/x")
    StateChoiceAssignWidgetInput(state_call=call)
    with pytest.raises(ValueError, match="exactly one of state_path or state_call"):
        StateChoiceAssignWidgetInput()
    with pytest.raises(ValueError, match="exactly one of state_path or state_call"):
        StateChoiceAssignWidgetInput(state_path="/x", state_call=call)
