"""A registry for the states of the actors."""

from rekuest_next.api.schema import (
    StateSchemaInput,
)
from typing import Any, Dict
from pydantic import Field
from koil.composition import KoiledModel
import json
from rekuest_next.structures.registry import StructureRegistry
import hashlib
from rekuest_next.structures.types import JSONSerializable


GLOBAL_STATE_REGISTRY = None


class StateRegistry(KoiledModel):
    """The state registry is used to register the states of the actors."""

    state_schemas: Dict[str, StateSchemaInput] = Field(
        default_factory=dict, exclude=True
    )
    registry_schemas: Dict[str, StructureRegistry] = Field(
        default_factory=dict, exclude=True
    )

    def register_at_name(
        self, name: str, state_schema: StateSchemaInput, registry: StructureRegistry
    ) -> None:
        """Register a state schema at a name."""
        self.state_schemas[name] = state_schema
        self.registry_schemas[name] = registry

    def get_schema_for_name(self, name: str) -> StateSchemaInput:
        """Get the schema for a name."""
        assert name in self.state_schemas, "No definition for interface"
        return self.state_schemas[name]

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
        return hashlib.sha256(
            json.dumps(self.dump(), sort_keys=True).encode()
        ).hexdigest()


def get_default_state_registry() -> "StateRegistry":
    """Get the default state registry."""
    global GLOBAL_STATE_REGISTRY
    if GLOBAL_STATE_REGISTRY is None:
        GLOBAL_STATE_REGISTRY = StateRegistry()  # type: ignore
    return GLOBAL_STATE_REGISTRY
