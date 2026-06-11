"""Top-level public API for rekuest_next.

Import application-facing decorators, runtime helpers, remote-call utilities,
and registry helpers from this module instead of reaching into internal
subpackages. The imported names below are the supported convenience surface for
agent applications.

The exports are grouped loosely into four categories:

- registration decorators such as ``declare``, ``state``, ``startup``, and
    ``background``
- runtime helpers such as ``log``, ``progress``, ``pausepoint``, and ``context``
- remote execution helpers such as ``find``, ``call``, ``acall``, and
    ``iterate``
- registry helpers such as ``AppRegistry`` and the default-app-registry accessors

Examples:
        Import the common decorators and helpers from one place::

                from rekuest_next import background, declare, jsx, log, startup

                @startup
                async def boot() -> None:
                        log("agent starting")

                panel = jsx("<Panel><Label text=\"ready\" /></Panel>")
"""

from .blok.parser import jsx
from .remote import (
    acall,
    call,
    acall_raw,
    acall_dependency,
    acall_dependency_raw,
    call_dependency_raw,
    call_dependency,
    call_raw,
    aiterate,
    iterate,
    find,
)
from .agents.context import context
from .agents.hooks.startup import startup
from .agents.hooks.background import background
from .actors.context import (
    log,
    alog,
    progress,
    aprogress,
    apausepoint,
    pausepoint,
    install_hook,
)
from .declare import declare, declare_state
from .structures.model import model, model_field
from .structures.decorator import structure
from .state.decorator import state
from .app import (
    AppRegistry,
    get_default_app_registry,
    set_default_app_registry,
    reset_default_app_registry,
)
from rekuest_next.annotations import Requires, Provides

try:
    from .arkitekt import RekuestNextService
except ImportError:
    pass


from .builtin_structures import structure_reg

__version__ = "0.4.1"

__all__ = [
    # registration decorators
    "declare",
    "declare_state",
    "state",
    "context",
    "startup",
    "background",
    "model",
    "model_field",
    "structure",
    "jsx",
    # runtime helpers
    "log",
    "alog",
    "progress",
    "aprogress",
    "pausepoint",
    "apausepoint",
    "install_hook",
    # remote execution helpers
    "find",
    "call",
    "acall",
    "call_raw",
    "acall_raw",
    "call_dependency",
    "acall_dependency",
    "acall_dependency_raw",
    "call_dependency_raw",
    "iterate",
    "aiterate",
    # registry helpers
    "AppRegistry",
    "structure_reg",
    "get_default_app_registry",
    "set_default_app_registry",
    "reset_default_app_registry",
    "Requires",
    "Provides",
    "RekuestNextService",
]
