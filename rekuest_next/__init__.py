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
    aiterate,
    iterate,
    find,
    acall_raw,
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
from .declare import declare, agent_protocol, declare_state
from .structures.model import model, model_field
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


from .structure import structure_reg

__version__ = "0.4.1"

__all__ = [
    "acall",
    "call",
    "log",
    "jsx",
    "alog",
    "progress",
    "aprogress",
    "declare",
    "agent_protocol",
    "model",
    "model_field",
    "state",
    "install_hook",
    "pausepoint",
    "apausepoint",
    "context",
    "model_field",
    "state",
    "background",
    "startup",
    "declare_state",
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
    "Requires",
    "Provides",
    "get_default_app_registry",
    "set_default_app_registry",
    "reset_default_app_registry",
]
