"""Check the logic of the Identifier scalar"""

from rekuest_next.scalars import Identifier
import pydantic
from pydantic import ValidationError
import pytest


class Serializing(pydantic.BaseModel):
    """Test class for the Identifier scalar"""

    identifier: Identifier


def test_identifier() -> None:
    """Test if the Identifier scalar works as expected"""
    Serializing(identifier="hm/test")


def test_wrong_identifier() -> None:
    """Test if the Identifier scalar works as expected"""
    with pytest.raises(ValidationError):
        Serializing(identifier="@dffest")
