from rekuest.scalars import Identifier
import pydantic
from pydantic import ValidationError
import pytest


class Serializing(pydantic.BaseModel):
    identifier: Identifier

    class Config:
        arbitrary_types_allowed = True


def test_identifier():
    Serializing(identifier="hm/test")


def test_wrong_identifier():
    with pytest.raises(ValidationError):
        Serializing(identifier="@dffest")
