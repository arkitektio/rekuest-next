"""A registry for the states of the actors."""

from rekuest_next.api.schema import (
    StateSchemaInput,
)
from typing import Any, Dict, Type
from pydantic import Field
from koil.composition import KoiledModel
import json
from rekuest_next.protocols import AnyState
from rekuest_next.structures.registry import StructureRegistry
import hashlib
from rekuest_next.structures.types import JSONSerializable


GLOBAL_STATE_REGISTRY = None


class StateRegistry(KoiledModel):
    """The state registry is used to register the states of the actors."""

    state_schemas: Dict[str, StateSchemaInput] = Field(default_factory=dict, exclude=True)
    registry_schemas: Dict[str, StructureRegistry] = Field(default_factory=dict, exclude=True)
    interface_classes: Dict[str, AnyState] = Field(default_factory=dict, exclude=True)
    classes_interfaces: Dict[Type[AnyState], str] = Field(default_factory=lambda: {}, exclude=True)

    def register_at_interface(
        self,
        interface: str,
        cls: Type[AnyState],
        state_schema: StateSchemaInput,
        registry: StructureRegistry,
    ) -> None:
        """Register a state schema at a name."""
        self.state_schemas[interface] = state_schema
        self.registry_schemas[interface] = registry
        self.classes_interfaces[cls] = interface
        self.interface_classes[interface] = cls

    def get_schema_for_interface(self, interface: str) -> StateSchemaInput:
        """Get the schema for a name."""
        assert interface in self.state_schemas, "No definition for interface"
        return self.state_schemas[interface]

    def get_registry_for_interface(self, interface: str) -> StructureRegistry:
        """Get the registry for a name."""
        assert interface in self.registry_schemas, "No definition for interface"
        return self.registry_schemas[interface]

    def get_interface_for_class(self, cls: Type[AnyState]) -> str:
        """Get the interface for a class."""
        assert cls in self.classes_interfaces, "No definition for class"
        return self.classes_interfaces[cls]

    async def __aenter__(self) -> "StateRegistry":
        """Enter the state registry context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any | None,  # noqa: ANN401
    ) -> None:
        """Exit the state registry context manager."""
        return

    def dump(self) -> list[JSONSerializable]:
        """Dump the state registry to a JSON-serializable format."""
        serialized_states = [
            json.loads(x.model_dump_json(exclude_none=True, exclude_unset=True))
            for x in self.state_schemas.values()
        ]

        return [serialized_states]

    def hash(self) -> str:
        """A hash of the state registry, used to check if the state registry has changed"""
        return hashlib.sha256(json.dumps(self.dump(), sort_keys=True).encode()).hexdigest()


def get_default_state_registry() -> "StateRegistry":
    """Get the default state registry."""
    global GLOBAL_STATE_REGISTRY
    if GLOBAL_STATE_REGISTRY is None:
        GLOBAL_STATE_REGISTRY = StateRegistry()  # type: ignore
    return GLOBAL_STATE_REGISTRY
