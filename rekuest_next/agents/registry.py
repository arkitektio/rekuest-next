"""An extension registry for the agent."""

import contextvars
from typing import Dict

from rekuest_next.agents.extension import AgentExtension
from rekuest_next.agents.extensions.default import DefaultExtension

Params = Dict[str, str]


current_extension_registry = contextvars.ContextVar("current_service_registry", default=None)
GLOBAL_EXTENSION_REGISTRY = None


class ExtensionRegistry:
    """A registry of extensions.

    This registry is used to store the extensions of the agent
    """

    def __init__(self) -> None:
        """Initialize the registry."""
        self.agent_extensions: Dict[str, AgentExtension] = {}

    def register(
        self,
        extension: AgentExtension,
    ) -> None:
        """Register an extension in the registry.
        This will register the extension in the registry and
        will also register the extension in the current extension registry.
        """
        name = extension.get_name()

        if name not in self.agent_extensions:
            self.agent_extensions[name] = extension
        else:
            raise ValueError(f"Extensions {name} already registered")

    def get(self, name: str) -> AgentExtension:
        """Get the extension by name."""
        return self.agent_extensions[name]


def get_default_extension_registry() -> ExtensionRegistry:
    """Get the default extension registry.
    This will create the registry if it does not exist.
    """
    global GLOBAL_EXTENSION_REGISTRY
    if GLOBAL_EXTENSION_REGISTRY is None:
        GLOBAL_EXTENSION_REGISTRY = ExtensionRegistry()  # type: ignore
        GLOBAL_EXTENSION_REGISTRY.register(DefaultExtension())
    return GLOBAL_EXTENSION_REGISTRY
