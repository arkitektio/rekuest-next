"""Functions for testing"""

from rekuest_next.widgets import withChoices, withDescription, withDefault
from typing import Annotated
from annotated_types import Len


X = Annotated[str, Len(min_length=3, max_length=5)]


def annotated_x(x: X) -> X:
    """Function that takes an annotated string."""
    return x


ChoiceX = Annotated[
    list[str], withChoices("a", "b", "c"), withDefault("a"), withDescription("A choice list")
]


def annotated_choice_x(x: ChoiceX) -> ChoiceX:
    """Function that takes an annotated choice list."""
    return x
