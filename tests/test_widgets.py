from rekuest_next.widgets import SearchWidget, SliderWidget
from pydantic import ValidationError
import pytest


def test_search_widget_error_on_wrong_graphql() -> None:
    """Test the search widget error when the GraphQL query is wrong"""
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
