from rekuest_next.api.schema import (
    AssignWidgetInput,
    ReturnWidgetInput,
    ChoiceInput,
    AssignWidgetKind,
    ValidatorFunction,
    ValidatorInput,
    EffectInput,
    EffectKind,
    ValidatorInput,
    PortGroupInput,
    ReturnWidgetKind,
)
from rekuest_next.scalars import SearchQuery
from typing import List, Optional


def SliderWidget(min: int = None, max: int = None, **kwargs) -> AssignWidgetInput:
    """Generate a slider widget.

    Args:
        min (int, optional): The mininum value. Defaults to None.
        max (int, optional): The maximum value. Defaults to None.

    Returns:
        WidgetInput: _description_
    """
    return AssignWidgetInput(kind=AssignWidgetKind.SLIDER, min=min, max=max, **kwargs)


def SearchWidget(query: SearchQuery, ward: str, **kwargs) -> AssignWidgetInput:
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
    """ """P"""
    return AssignWidgetInput(
        kind=AssignWidgetKind.SEARCH, query=query, ward=ward, **kwargs
    )


def StringWidget(as_paragraph: bool = False, **kwargs) -> AssignWidgetInput:
    """Generate a string widget.

    Args:
        as_paragraph (bool, optional): Should we render the string as a paragraph.Defaults to False.

    Returns:
        WidgetInput: _description_
    """
    return AssignWidgetInput(
        kind=AssignWidgetKind.STRING, asParagraph=as_paragraph, **kwargs
    )


def ParagraphWidget(**kwargs) -> AssignWidgetInput:
    """Generate a string widget.

    Args:
        as_paragraph (bool, optional): Should we render the string as a paragraph.Defaults to False.

    Returns:
        WidgetInput: _description_
    """
    return AssignWidgetInput(kind=AssignWidgetKind.STRING, asParagraph=True, **kwargs)


def CustomWidget(hook: str, **kwargs) -> AssignWidgetInput:
    """Generate a custom widget.

    A custom widget is a widget that is rendered by a frontend registered hook
    that is passed the input value.

    Args:
        hook (str): The hook key

    Returns:
        WidgetInput: _description_
    """
    return AssignWidgetInput(kind=AssignWidgetKind.CUSTOM, hook=hook, **kwargs)


def CustomReturnWidget(hook: str, **kwargs) -> ReturnWidgetInput:
    """A custom return widget.

    A custom return widget is a widget that is rendered by a frontend registered hook
    that is passed the input value.

    Args:
        hook (str): The hool

    Returns:
        ReturnWidgetInput: _description_
    """ """"""
    return ReturnWidgetInput(kind=ReturnWidgetKind.CUSTOM, hook=hook, **kwargs)


def ChoiceReturnWidget(choices: List[ChoiceInput], **kwargs) -> ReturnWidgetInput:
    """A choice return widget.

    A choice return widget is a widget that renderes a list of choices with the
    value of the choice being highlighted.

    Args:
        choices (List[ChoiceInput]): The choices

    Returns:
        ReturnWidgetInput: _description_
    """
    return ReturnWidgetInput(kind=ReturnWidgetKind.CHOICE, choices=choices, **kwargs)



def ChoiceWidget(choices: List[ChoiceInput], **kwargs) -> AssignWidgetInput:
    """A state choice widget.

    A state choice widget is a widget that renders a list of choices with the
    value of the choice being highlighted.

    Args:
        stateChoices (str): The state key that contains the choices
        followValue (str): The state key that the value should be followed

    Returns:
        AssignWidgetInput: The widget input
    """
    return AssignWidgetInput(
        kind=AssignWidgetKind.CHOICE,
        choices=choices,
        **kwargs,
    )

