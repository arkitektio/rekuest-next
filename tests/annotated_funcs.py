"""Functions for testing"""

from rekuest_next.widgets import withChoices
from rekuest_next import Description, Default
from typing import Annotated
from annotated_types import Len


X = Annotated[str, Len(min_length=3, max_length=5)]


def annotated_x(x: X) -> X:
    """Function that takes an annotated string."""
    return x


ChoiceX = Annotated[
    list[str],
    withChoices("a", "b", "c"),
    Default("a"),
    Description("A choice list"),
]


def annotated_choice_x(x: ChoiceX) -> ChoiceX:
    """Function that takes an annotated choice list."""
    return x
