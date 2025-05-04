"""Test the PortInput class  and its validation logic."""

from rekuest_next.api.schema import PortInput, PortKind
from pydantic import ValidationError
import pytest


def test_argport_input_errors() -> None:
    """Test invalid PortInput instances"""
    with pytest.raises(ValidationError):
        # kind is required and only accepts PortKind
        PortInput(kind="lala")

    with pytest.raises(ValidationError):
        # key and nullable are required
        PortInput(kind=PortKind.BOOL)

    with pytest.raises(ValidationError):
        # nullable is required
        PortInput(kind=PortKind.BOOL, key="search")

    with pytest.raises(ValidationError):
        # identifier is required for STRUCTURE
        PortInput(kind=PortKind.STRUCTURE, key="search", nullable=False)

    with pytest.raises(ValidationError):
        # child is required for List
        PortInput(kind=PortKind.LIST, key="search", nullable=False)


def test_argport() -> None:
    """Test valid PortInput instances"""
    PortInput(kind=PortKind.BOOL, key="search", nullable=False)
    PortInput(kind=PortKind.STRING, key="search", nullable=False)

    PortInput(
        kind=PortKind.STRUCTURE,
        identifier="hm/karl",
        key="search",
        nullable=False,
    )

    PortInput(
        kind=PortKind.LIST,
        children=[PortInput(key="0", kind=PortKind.BOOL, nullable=False)],
        nullable=False,
        key="search",
    )
