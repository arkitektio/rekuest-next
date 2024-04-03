from rekuest.widgets import SearchWidget, SliderWidget
from pydantic import ValidationError
import pytest


def test_search_widget_error_on_wrong_graphql():
    with pytest.raises(ValidationError):
        SearchWidget(query="hallo", ward="mikro")

    with pytest.raises(ValidationError):
        SearchWidget(query="query search {}", ward="mikro")

    with pytest.raises(ValidationError):
        SearchWidget(query="query search($name: sss) {}", ward="mikro")

    with pytest.raises(ValidationError):
        SearchWidget(
            query="query search($search: String) {lala {value: x label: y}}",
            ward="mikro",
        )

    with pytest.raises(ValidationError):
        SearchWidget(
            query="query search($search: String) {options: karl {x label: y}}",
            ward="mikro",
        )


def test_search_widget():
    SearchWidget(
        query=(
            "query search($search: String, $values: [ID]){ options: karl { value: x"
            " label: y}} "
        ),
        ward="mikro",
    )


def test_slider_widget_error():
    with pytest.raises(ValidationError):
        SliderWidget(min=1, max=0)

    with pytest.raises(ValidationError):
        SliderWidget(min=0)


def test_slider_widget():
    SliderWidget(
        min=0,
        max=100,
    )
