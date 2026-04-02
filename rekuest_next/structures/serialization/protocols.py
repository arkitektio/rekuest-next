"""Just a protocol for the serialization of ports."""

from typing import Union
from rekuest_next.api.schema import (
    ArgPort,
    ReturnPort,
    ArgChildPort,
    ReturnChildPort,
    ArgChildPortNested,
    ReturnChildPortNested,
)

SerializablePort = Union[
    ArgPort,
    ReturnPort,
    ArgChildPort,
    ReturnChildPort,
    ArgChildPortNested,
    ReturnChildPortNested,
]
