import contextvars
from typing import Dict

from rekuest_next.agents.extension import AgentExtension
from rekuest_next.agents.extensions.default import DefaultExtension

Params = Dict[str, str]


current_extension_registry = contextvars.ContextVar(
    "current_service_registry", default=None
)
GLOBAL_EXTENSION_REGISTRY = None


def get_default_extension_registry():
    global GLOBAL_EXTENSION_REGISTRY
    if GLOBAL_EXTENSION_REGISTRY is None:
        GLOBAL_EXTENSION_REGISTRY = ExtensionRegistry()
        GLOBAL_EXTENSION_REGISTRY.register(DefaultExtension())
    return GLOBAL_EXTENSION_REGISTRY


def get_current_extension_registry(allow_global=True):
    return current_extension_registry.get(get_default_extension_registry())


class ExtensionRegistry:
    def __init__(self, import_services=True):
        self.agent_extensions: Dict[str, AgentExtension] = {}

    def register(
        self,
        extension: AgentExtension,
    ):

        name = extension.get_name()

        if name not in self.agent_extensions:
            self.agent_extensions[name] = extension
        else:
            raise ValueError(f"Extensions {name} already registered")

   
    def get(self, name):
        return self.agent_extensions.get(name)

