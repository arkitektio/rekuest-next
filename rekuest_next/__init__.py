"""This module provides the main interface for the Rekuest library.
It includes the main classes and functions for creating and managing
Rekuest instances, as well as utility functions for working with
Rekuest objects.
"""

from .remote import (
    acall,
    call,
    aiterate,
    iterate,
    find,
    acall_raw,
)
from .declare import declare, protocol
from .structures.model import model
from .state.decorator import state

try:
    from .arkitekt import RekuestNextService
except ImportError as e:
    raise e


from .structure import structure_reg

__version__ = "0.4.1"

__all__ = [
    "acall",
    "state",
    "find",
    "RekuestNextService",
    "call",
    "structure_reg",
    "iterate",
    "aiterate",
    "model",
    "acall_raw",
    "structure_reg",
]
