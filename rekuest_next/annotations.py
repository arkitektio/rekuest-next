"""Additional type hinting classes for Rekuest, that can be used to annotate port groups"""

from typing import Any, TypeVar
from rekuest_next.api.schema import RequiresInput, ProvidesInput

T = TypeVar("T")


class Description:
    """Description class for type hinting.

    This class is used to provide a description for a type. It is used in the
    `description` parameter of the `@context` decorator.
    """

    def __init__(self, description: str) -> None:
        """Initialize the Description class.
        Args:
            description (str): The description for the type.
        """
        self.description = description

    def __repr__(self) -> str:
        """Return a string representation of the Description class.
        Returns:
            str: A string representation of the Description class.
        """
        return f"Description({self.description})"


class Requires(RequiresInput):
    """Requires class for type hinting.

    This class is used to provide a description for a required port group. It is used in the
    `requires` parameter of the `@context` decorator.
    """

    def __repr__(self) -> str:
        """Return a string representation of the Requires class.
        Returns:
            str: A string representation of the Requires class.
        """
        return f"Requires({self.key}, {self.operator}, {self.value})"


class Provides(ProvidesInput):
    """Provides class for type hinting.

    This class is used to provide a description for a provided port group. It is used in the
    `provides` parameter of the `@context` decorator.
    """

    def __repr__(self) -> str:
        """Return a string representation of the Provides class.
        Returns:
            str: A string representation of the Provides class.
        """
        return f"Provides({self.key}    , {self.operator}, {self.value})"
