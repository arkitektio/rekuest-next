from rekuest_next.state.predicate import get_state_name, is_state
from rekuest_next.structures.model import model
from typing import Optional, Type, TypeVar, Callable
from typing import Dict, Any
import inspect
from fieldz import fields
from rekuest_next.structures.registry import (
    StructureRegistry,
    get_current_structure_registry,
)

from rekuest_next.state.registry import (
    StateRegistry,
    get_default_state_registry,
    get_current_state_registry,
)
from rekuest_next.api.schema import StateSchemaInput
from rekuest_next.structures.default import get_default_structure_registry

T = TypeVar("T")


def inspect_state_schema(
    cls: Type[T], structure_registry: StructureRegistry
) -> Optional[StateSchemaInput]:
    from rekuest_next.definition.define import convert_object_to_port

    ports = []

    for field in fields(cls):
        port = convert_object_to_port(field.type, field.name, structure_registry)
        ports.append(port)

    return StateSchemaInput(ports=ports, name=cls.__rekuest_state__)


def state(
    name: str,
    registry: Optional[StateRegistry] = None,
    structure_reg: Optional[StructureRegistry] = None,
) -> Callable[[Type[T]], Type[T]]:

    registry = registry or get_current_state_registry()
    structure_registry = structure_reg or get_default_structure_registry()

    def wrapper(cls: Type[T]) -> Type[T]:

        setattr(cls, "__rekuest_state__", name)

        state_schema = inspect_state_schema(cls, structure_registry)

        registry.register_at_name(name, state_schema, structure_registry)

        return cls

    return wrapper


def prepare_state_variables(function) -> Dict[str, Any]:

    sig = inspect.signature(function)
    parameters = sig.parameters

    state_variables = {}
    state_returns = {}

    for key, value in parameters.items():
        if is_state(value.annotation):
            state_variables[key] = get_state_name(value.annotation)

    returns = sig.return_annotation

    if hasattr(returns, "_name"):
        if returns._name == "Tuple":
            for index, cls in enumerate(returns.__args__):
                if is_state(cls):
                    state_returns[index] = get_state_name(value)
        else:
            if is_state(returns):
                state_returns[0] = get_state_name(value)

    return state_variables, state_returns
