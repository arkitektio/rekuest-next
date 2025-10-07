"""Register a function or actor with the definition registry."""

from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    ParamSpec,
    Tuple,
    TypeVar,
    Union,
    overload,
    cast,
)
import inflection
from rekuest_next.actors.errors import NotWithinAnAssignationError
from rekuest_next.remote import call
from rekuest_next.actors.actify import reactify
from rekuest_next.actors.sync import SyncGroup
from rekuest_next.actors.types import Actifier, ActorBuilder, OnProvide, OnUnprovide
from rekuest_next.actors.vars import get_current_assignation_helper
from rekuest_next.definition.define import AssignWidgetMap, prepare_definition
from rekuest_next.definition.hash import hash_definition
from rekuest_next.definition.registry import (
    DefinitionRegistry,
    get_default_definition_registry,
)
from rekuest_next.protocols import AnyFunction
from rekuest_next.structures.default import get_default_structure_registry
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.api.schema import (
    AssignWidgetInput,
    DefinitionInput,
    ActionDependencyInput,
    PortGroupInput,
    EffectInput,
    ImplementationInput,
    PortInput,
    PortMatchInput,
    ValidatorInput,
    my_implementation_at,
    PortMatchInput,
    get_implementation,
)


def interface_name(func: AnyFunction) -> str:
    """Infer an interface name from a function or actor name.

    Converts CamelCase or mixedCase names to snake_case.

    Args:
        func (AnyFunction): The function or actor to infer the name from.

    Returns:
        str: The inferred interface name in snake_case.
    """
    return inflection.underscore(func.__name__)


P = ParamSpec("P")
R = TypeVar("R")


class DeclaredFunction(Generic[P, R]):
    """A wrapped function that calls the actor's implementation."""

    def __init__(self, func: AnyFunction) -> None:
        """Initialize the wrapped function."""
        self.func = func
        self.definition = prepare_definition(
            func,
            structure_registry=get_default_structure_registry(),
        )

    def call(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """ "Call the actor's implementation."""
        helper = get_current_assignation_helper()
        dependency = helper.get_dependency(
            interface_name(self.func),
        )

        implementation = get_implementation(dependency)

        return call(implementation, *args, parent=helper.assignment, **kwargs)

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """ "Call the wrapped function directly if not within an assignation."""
        return self.call(*args, **kwargs)

    def to_dependency_input(self) -> ActionDependencyInput:
        """Convert the wrapped function to a DependencyInput."""
        return ActionDependencyInput(
            optional=False,
            key=interface_name(self.func),
            hash=hash_definition(self.definition),
        )


def port_to_match(index: int, port: PortInput) -> PortMatchInput:
    return PortMatchInput(
        at=index,
        key=port.key,
        identifier=port.identifier,
        kind=port.kind,
        nullable=port.nullable,
        children=[
            port_to_match(index, child)
            for index, child in enumerate(port.children or [])
        ]
        if port.children
        else None,
    )


class DeclaredProtocol(Generic[P, R]):
    """A wrapped function that calls the actor's implementation."""

    def __init__(self, func: AnyFunction) -> None:
        """Initialize the wrapped function."""
        self.func = func
        self.definition = prepare_definition(
            func,
            structure_registry=get_default_structure_registry(),
        )

    def call(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """ "Call the actor's implementation."""
        helper = get_current_assignation_helper()
        dependency = helper.get_dependency(
            interface_name(self.func),
        )

        implementation = get_implementation(dependency)

        return call(implementation, *args, parent=helper.assignment, **kwargs)

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """ "Call the wrapped function directly if not within an assignation."""
        return self.call(*args, **kwargs)

    def to_dependency_input(self) -> ActionDependencyInput:
        """Convert the wrapped function to a DependencyInput."""

        arg_matches: list[PortMatchInput] = []
        return_matches: list[PortMatchInput] = []

        for index, arg in enumerate(self.definition.args):
            arg_matches.append(port_to_match(index, arg))

        for index, ret in enumerate(self.definition.returns):
            return_matches.append(port_to_match(index, ret))

        return ActionDependencyInput(
            optional=False,
            key=interface_name(self.func),
            description=self.definition.description,
            arg_matches=arg_matches,
            return_matches=return_matches,
        )


def declare(func: Callable[P, R]) -> DeclaredFunction[P, R]:
    """Declare a function or actor without registering it.

    This is useful for testing or for defining functions that will be registered later.

    Args:
        func (Callable[P, R]): The function or actor to declare.

    Returns:
        WrappedFunction[P, R]: A wrapped function that can be called directly or via the actor system.
    """
    return DeclaredFunction(func=func)


def protocol(func: Callable[P, R]) -> DeclaredFunction[P, R]:
    """Declare a function or actor without registering it.

    This is useful for testing or for defining functions that will be registered later.

    Args:
        func (Callable[P, R]): The function or actor to declare.

    Returns:
        WrappedFunction[P, R]: A wrapped function that can be called directly or via the actor system.
    """
    return DeclaredProtocol(func=func)
