"""Additional type hinting classes for Rekuest, that can be used to annotate port groups"""

from typing import TypeVar

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


class Label:
    """Label class for type hinting.

    This class is used to provide a label for a type. It is used in the
    `label` parameter of the `@context` decorator.
    """

    def __init__(self, label: str) -> None:
        """Initialize the Label class.
        Args:
            label (str): The label for the type.
        """
        self.label = label

    def __repr__(self) -> str:
        """Add a string representation of the Label class.

        Returns:
            str: A string representation of the Label class.
        """
        return f"Label({self.label})"
