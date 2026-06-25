"""Tests for the SearchWidget filter ports and dependency validation.

A custom search widget may declare GraphQL query variables beyond the mandatory
``$search``/``$values``. Each extra variable must be backed (by exact name) by
either one of the widget's own filter ports or a neighbouring-port dependency.
The dependency case is additionally validated against the sibling ports when the
definition is built.
"""

from pydantic import ValidationError
import pytest

from rekuest_next.widgets import SearchWidget
from rekuest_next.api.schema import ArgPortInput, PortKind
from rekuest_next.definition.define import prepare_definition
from rekuest_next.structures.registry import StructureRegistry


# A query that declares one extra variable ($dataset) on top of the mandatory ones.
QUERY_WITH_DATASET = (
    "query search($search: String, $values: [ID], $dataset: ID) {"
    " options: images(dataset: $dataset, search: $search, ids: $values) {"
    " value: id label: name } }"
)

# A query whose extra variable is named after the first return port ($return0).
QUERY_WITH_RETURN0 = (
    "query search($search: String, $values: [ID], $return0: ID) {"
    " options: images(parent: $return0, search: $search, ids: $values) {"
    " value: id label: name } }"
)

# A plain query with only the mandatory variables.
PLAIN_QUERY = (
    "query search($search: String, $values: [ID]) {"
    " options: images(search: $search, ids: $values) { value: id label: name } }"
)

# A query using the reserved pagination variables ($limit/$offset).
QUERY_WITH_PAGINATION = (
    "query search($search: String, $values: [ID], $limit: Int, $offset: Int) {"
    " options: images(search: $search, ids: $values, pagination: {limit: $limit, offset: $offset}) {"
    " value: id label: name } }"
)


# --- Widget-level validation (constructing SearchWidget directly) --------------


def test_extra_variable_backed_by_filter_port() -> None:
    """An extra query variable backed by a matching filter port is accepted."""
    widget = SearchWidget(
        query=QUERY_WITH_DATASET,
        ward="mikro",
        filters=[ArgPortInput(key="dataset", kind=PortKind.STRING, nullable=True)],
    )
    assert widget.filters is not None
    assert widget.filters[0].key == "dataset"


def test_extra_variable_backed_by_dependency() -> None:
    """An extra query variable backed by a declared dependency is accepted."""
    widget = SearchWidget(
        query=QUERY_WITH_DATASET,
        ward="mikro",
        dependencies=["dataset"],
    )
    assert widget.dependencies == ("dataset",)


def test_extra_variable_without_backing_is_rejected() -> None:
    """An extra query variable with neither a filter nor a dependency errors."""
    with pytest.raises(ValidationError, match="dataset"):
        SearchWidget(query=QUERY_WITH_DATASET, ward="mikro")


def test_plain_query_needs_no_filters_or_dependencies() -> None:
    """A query with only $search/$values needs nothing extra (regression)."""
    widget = SearchWidget(query=PLAIN_QUERY, ward="mikro")
    assert widget.filters is None
    assert widget.dependencies is None


def test_reserved_pagination_variables_need_no_backing() -> None:
    """The reserved $limit/$offset pagination variables need no filter/dependency."""
    widget = SearchWidget(query=QUERY_WITH_PAGINATION, ward="mikro")
    assert widget.filters is None
    assert widget.dependencies is None


def test_filter_port_name_must_match_variable_exactly() -> None:
    """A filter port whose key differs from the variable name does not back it."""
    with pytest.raises(ValidationError, match="dataset"):
        SearchWidget(
            query=QUERY_WITH_DATASET,
            ward="mikro",
            filters=[ArgPortInput(key="other", kind=PortKind.STRING, nullable=True)],
        )


# --- Definition-level validation (dependency -> neighbouring port) -------------


def test_dependency_resolves_to_neighbouring_arg(
    simple_registry: StructureRegistry,
) -> None:
    """A search-widget dependency pointing at a sibling arg port is accepted."""

    def search_image(image: str, dataset: str) -> str:
        """Search for an image within a dataset."""
        return image

    definition = prepare_definition(
        search_image,
        structure_registry=simple_registry,
        widgets={
            "image": SearchWidget(
                query=QUERY_WITH_DATASET, ward="mikro", dependencies=["dataset"]
            )
        },
    )

    widget = definition.args[0].widget
    assert widget is not None
    assert widget.dependencies == ("dataset",)


def test_dependency_without_neighbouring_port_is_rejected(
    simple_registry: StructureRegistry,
) -> None:
    """A dependency that matches no sibling port fails when the definition builds."""

    def search_image(image: str) -> str:
        """Search for an image, depending on a non-existent 'dataset' port."""
        return image

    with pytest.raises(ValidationError, match="dataset"):
        prepare_definition(
            search_image,
            structure_registry=simple_registry,
            widgets={
                "image": SearchWidget(
                    query=QUERY_WITH_DATASET, ward="mikro", dependencies=["dataset"]
                )
            },
        )


def test_dependency_resolves_to_return_port(
    simple_registry: StructureRegistry,
) -> None:
    """A dependency may resolve to a return port key (e.g. 'return0')."""

    def search_image(image: str) -> str:
        """Search for an image, depending on the first return port."""
        return image

    definition = prepare_definition(
        search_image,
        structure_registry=simple_registry,
        widgets={
            "image": SearchWidget(
                query=QUERY_WITH_RETURN0, ward="mikro", dependencies=["return0"]
            )
        },
    )

    assert definition.returns[0].key == "return0"
    widget = definition.args[0].widget
    assert widget is not None
    assert widget.dependencies == ("return0",)
