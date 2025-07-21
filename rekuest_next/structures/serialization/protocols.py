"""Just a protocol for the serialization of ports."""

from typing import Union
from rekuest_next.api.schema import (
    Port,
    ChildPort,
    ChildPortNested,
    ChildPortNestedChildren,
)

SerializablePort = Union[Port, ChildPort, ChildPortNested, ChildPortNestedChildren]
