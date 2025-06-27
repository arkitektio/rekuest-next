"""Some basic helpers to create common widgets."""

from rekuest_next.api.schema import (
    AssignWidgetInput,
    ReturnWidgetInput,
    ChoiceInput,
    PortInput,
    AssignWidgetKind,
    ReturnWidgetKind,
    ValidatorFunction,
    ValidatorInput,
)
from rekuest_next.scalars import SearchQuery
from typing import List


def SliderWidget(
    min: int | None = None, max: int | None = None, step: int | None = None
) -> AssignWidgetInput:
    """Generate a slider widget.

    Args:
        min (int, optional): The mininum value. Defaults to None.
        max (int, optional): The maximum value. Defaults to None.

    Returns:
        WidgetInput: _description_
    """
    return AssignWidgetInput(kind=AssignWidgetKind.SLIDER, min=min, max=max, step=step)


def SearchWidget(
    query: SearchQuery | str,
    ward: str,
    dependencies: list[str] | None = None,
    filters: list[PortInput] | None = None,
) -> AssignWidgetInput:
    (
        """Generte a search widget.

    A search widget is a widget that allows the user to search for a specifc
    structure utilizing a GraphQL query and running it on a ward (a frontend 
    registered helper that can run the query). The query needs to follow
    the SearchQuery type.

    Args:
        query (SearchQuery): The serach query as a search query object or string
        ward (str): The ward key

    Returns:
        WidgetInput: _description_
    """
        """P"""
    )
    return AssignWidgetInput(
        kind=AssignWidgetKind.SEARCH,
        query=SearchQuery.validate(query),
        ward=ward,
        dependencies=tuple(dependencies) if dependencies else None,
        filters=tuple(filters) if filters else None,
    )


def StringWidget(as_paragraph: bool = False) -> AssignWidgetInput:
    """Generate a string widget.

    Args:
        as_paragraph (bool, optional): Should we render the string as a paragraph.Defaults to False.

    Returns:
        WidgetInput: _description_
    """
    return AssignWidgetInput(kind=AssignWidgetKind.STRING, asParagraph=as_paragraph)


def ParagraphWidget() -> AssignWidgetInput:
    """Generate a string widget.

    Args:
        as_paragraph (bool, optional): Should we render the string as a paragraph.Defaults to False.

    Returns:
        WidgetInput: _description_
    """
    return AssignWidgetInput(kind=AssignWidgetKind.STRING, asParagraph=True)


def CustomWidget(hook: str, ward: str) -> AssignWidgetInput:
    """Generate a custom widget.

    A custom widget is a widget that is rendered by a frontend registered hook
    that is passed the input value.

    Args:
        hook (str): The hook key

    Returns:
        WidgetInput: _description_
    """
    return AssignWidgetInput(kind=AssignWidgetKind.CUSTOM, hook=hook, ward=ward)


def CustomReturnWidget(hook: str, ward: str) -> ReturnWidgetInput:
    """A custom return widget.

    A custom return widget is a widget that is rendered by a frontend registered hook
    that is passed the input value.

    Args:
        hook (str): The hool
        ward (str): The ward key

    Returns:
        ReturnWidgetInput: The widget input
    """
    return ReturnWidgetInput(kind=ReturnWidgetKind.CUSTOM, hook=hook, ward=ward)


def ChoiceReturnWidget(choices: List[ChoiceInput]) -> ReturnWidgetInput:
    """A choice return widget.

    A choice return widget is a widget that renderes a list of choices with the
    value of the choice being highlighted.

    Args:
        choices (List[ChoiceInput]): The choices

    Returns:
        ReturnWidgetInput: _description_
    """
    return ReturnWidgetInput(kind=ReturnWidgetKind.CHOICE, choices=tuple(choices))


def ChoiceWidget(choices: List[ChoiceInput]) -> AssignWidgetInput:
    """A choice widget.

    A choice widget is a widget that renders a list of choices with the
    value of the choice being highlighted.

    Args:
        choices (list[ChoiceInput]): The choices

    Returns:
        AssignWidgetInput: The widget input
    """
    return AssignWidgetInput(kind=AssignWidgetKind.CHOICE, choices=tuple(choices))


def withChoices(
    *choices: ChoiceInput,
) -> AssignWidgetInput:
    """A decorator to add choices to a widget.

    Args:
        choices (List[ChoiceInput]): The choices

    Returns:
        AssignWidgetInput: The widget input
    """
    return AssignWidgetInput(kind=AssignWidgetKind.CHOICE, choices=tuple(choices))


def withValidator(
    function: str,
    errorMessage: str,
    dependencies: List[str] | None = None,
) -> ValidatorInput:
    """A decorator to add a validator to a widget.

    Args:
        function (str): The function to run
        errorMessage (str): The error message to show if the validation fails
        dependencies (List[str], optional): The dependencies of the validator. Defaults to None.

    Returns:
        AssignWidgetInput: The widget input
    """
    return ValidatorInput(
        function=ValidatorFunction.validate(function),
        errorMessage=errorMessage,
        dependencies=tuple(dependencies) if dependencies else None,
    )
