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
from .actors.context import log, alog, progress, aprogress, apausepoint, pausepoint
from .declare import declare, protocol
from .structures.model import model, model_field
from .state.decorator import state
from .app import (
    AppRegistry,
    get_default_app_registry,
    set_default_app_registry,
    reset_default_app_registry,
)

try:
    from .arkitekt import RekuestNextService
except ImportError:
    pass


from .structure import structure_reg

__version__ = "0.4.1"

__all__ = [
    "acall",
    "call",
    "log",
    "alog",
    "progress",
    "aprogress",
    "declare",
    "protocol",
    "model",
    "pausepoint",
    "apausepoint",
    "model_field",
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
    "AppRegistry",
    "get_default_app_registry",
    "set_default_app_registry",
    "reset_default_app_registry",
]
