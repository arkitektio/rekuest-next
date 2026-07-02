"""User-facing annotation markers for Rekuest ports.

These are the objects a user places inside :data:`typing.Annotated` to attach
extra metadata to a port -- a description, a default value, a proposed unit set,
or a requires/provides constraint. They are picked up by the annotation parsers
in :mod:`rekuest_next.annotations.parsers` while a callable is being defined.

All markers share a consistent PascalCase, callable surface and are re-exported
from the top-level :mod:`rekuest_next` package::

    from rekuest_next import Description, Default, Units, Requires, Provides

    def measure(
        exposure: Annotated[Duration, Units("ms", "s"), Description("Exposure time")],
    ) -> int: ...
"""

from typing import TypeVar

from rekuest_next.api.schema import ProvidesInput, RequiresInput
from rekuest_next.structures.types import JSONSerializable

T = TypeVar("T")


class Description:
    """Attach a human-readable description to a port.

    Use inside :data:`typing.Annotated` to override the description a port would
    otherwise take from the docstring::

        name: Annotated[str, Description("The user's full name")]
    """

    def __init__(self, value: str) -> None:
        """Initialize the Description marker with a value."""
        if not isinstance(value, str):  # type: ignore[reportUnnecessaryIsInstance]
            raise TypeError("Description value must be a string")
        self.value = value

    def __repr__(self) -> str:
        """Return a string representation of the Description marker."""
        return f"Description({self.value})"


class Default:
    """Attach a default value to a port.

    Use inside :data:`typing.Annotated` to give a port a default without adding a
    parameter default to the function signature::

        threshold: Annotated[int, Default(5)]
    """

    def __init__(self, value: JSONSerializable) -> None:
        """Initialize the Default marker with a value."""
        self.value = value

    def __repr__(self) -> str:
        """Return a string representation of the Default marker."""
        return f"Default(value={self.value})"


class Units:
    """Override the units a UI proposes for a ``QUANTITY`` port.

    Use on a kanne-typed parameter to replace the type's default proposed units::

        exposure: Annotated[Duration, Units("ms", "s")]

    Proposals only -- any unit of the same dimension is still valid input.
    """

    def __init__(self, *units: str) -> None:
        """Initialize with the units to propose (at least one)."""
        if not units:
            raise TypeError("Units requires at least one unit")
        self.units = list(units)

    def __repr__(self) -> str:
        """Return a string representation of the Units marker."""
        return f"Units({', '.join(map(repr, self.units))})"


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
