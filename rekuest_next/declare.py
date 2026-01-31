"""Register a function or actor with the definition registry."""

from typing import (
    Callable,
    Dict,
    Generic,
    List,
    ParamSpec,
    Type,
    TypeVar,
    Union,
    overload,
)
import inflection
from rekuest_next.api.schema import ActionKind
from rekuest_next.remote import call, call_dependency, iterate
from rekuest_next.actors.vars import get_current_assignation_helper
from rekuest_next.definition.define import prepare_definition
from rekuest_next.definition.hash import hash_definition
from rekuest_next.protocols import AnyFunction
from rekuest_next.structures.default import get_default_structure_registry
from rekuest_next.api.schema import (
    ActionDependencyInput,
    Implementation,
    PortInput,
    PortMatchInput,
    get_implementation,
    AgentDependencyInput,
)
import inspect


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

        if implementation.action.kind == ActionKind.FUNCTION:
            return call(implementation, *args, parent=helper.assignment, **kwargs)
        elif implementation.action.kind == ActionKind.GENERATOR:
            return iterate(implementation, *args, parent=helper.assignment, **kwargs)
        else:
            raise Exception(f"Cannot call implementation of kind {implementation.action.kind}")

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
        children=[port_to_match(index, child) for index, child in enumerate(port.children or [])]
        if port.children
        else None,
    )


class DeclaredProtocol(Generic[P, R]):
    """A wrapped function that calls the actor's implementation."""

    def __init__(
        self,
        func: AnyFunction,
        name: str | None = None,
        hash: str | None = None,
        optional: bool = False,
        description: str | None = None,
        allow_inactive: bool = True,
    ) -> None:
        """Initialize the wrapped function."""
        self.func = func
        self.definition = prepare_definition(
            func,
            structure_registry=get_default_structure_registry(),
        )
        self.name = name
        self.hash = hash
        self.optional = optional
        self.description = description
        self.allow_inactive = allow_inactive

    def call(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """ "Call the actor's implementation."""
        helper = get_current_assignation_helper()
        dependency = helper.get_dependency(
            interface_name(self.func),
        )

        implementation = get_implementation(dependency)

        if implementation.action.kind == ActionKind.FUNCTION:
            return call(implementation, *args, parent=helper.assignment, **kwargs)
        elif implementation.action.kind == ActionKind.GENERATOR:
            return iterate(implementation, *args, parent=helper.assignment, **kwargs)
        else:
            raise Exception(f"Cannot call implementation of kind {implementation.action.kind}")

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
            key=interface_name(self.func),
            description=self.description or self.definition.description,
            arg_matches=arg_matches,
            return_matches=return_matches,
            hash=self.hash,
            name=self.name,
            optional=self.optional,
            allow_inactive=True,
        )


class DeclaredAgentAction(Generic[P, R]):
    """A wrapped function that calls the actor's implementation."""

    def __init__(self, func: AnyFunction, agent_interface: str) -> None:
        """Initialize the wrapped function."""
        self.func = func
        self.agent_interface = agent_interface
        self.definition = prepare_definition(
            func,
            structure_registry=get_default_structure_registry(),
        )
        self.interface = interface_name(func)
        self._current_implementation_cache: Dict[str, List[Implementation]] = {}

    def call(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """ "Call the actor's implementation."""

        helper = get_current_assignation_helper()

        if self.definition.kind == ActionKind.FUNCTION:
            return call_dependency(
                self.definition,
                self.agent_interface,
                self.interface,
                *args,
                parent=helper.assignment,
                **kwargs,
            )
        elif self.definition.kind == ActionKind.GENERATOR:
            raise NotImplementedError("Generator actions are not supported in agent protocols.")
        else:
            raise Exception(f"Cannot call implementation of kind {self.definition.kind}")

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
            key=self.interface,
            description=self.definition.description,
            arg_matches=arg_matches,
            return_matches=return_matches,
            allow_inactive=True,
            name=self.definition.name,
            optional=False,
        )


Agent = TypeVar("Agent")


class DeclaredAgentProtocol(Generic[Agent]):
    """A wrapped function that calls the actor's implementation."""

    def __init__(
        self,
        func: Type[Agent],
        name: str | None = None,
        hash: str | None = None,
        optional: bool = False,
        description: str | None = None,
        allow_inactive: bool = True,
    ) -> None:
        """Initialize the wrapped function."""
        self.func = func
        self.name = name
        self.hash = hash
        self.optional = optional
        self.description = description or func.__doc__
        self.allow_inactive = allow_inactive
        self.interface = interface_name(func)
        self.actions = {}

        for name, method in inspect.getmembers(func):
            if not name.startswith("_") and callable(method):
                action = DeclaredAgentAction(method, self.interface)
                self.actions[name] = action
                setattr(self, name, action)

    def to_dependency_input(self) -> AgentDependencyInput:
        """Convert the wrapped function to a DependencyInput."""
        return AgentDependencyInput(
            key=self.interface,
            name=self.name,
            description=self.description or self.func.__doc__,
            action_demands=[action.to_dependency_input() for action in self.actions.values()],
            optional=self.optional,
            min_viable_instances=1,
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


@overload
def protocol(func: Callable[P, R]) -> DeclaredFunction[P, R]: ...


@overload
def protocol(
    *, name: str | None = None, hash: str | None = None
) -> Callable[[Callable[P, R]], DeclaredFunction[P, R]]: ...


def protocol(
    *func: Callable[P, R],
    name: str | None = None,
    hash: str | None = None,
    optional: bool = False,
    description: str | None = None,
    allow_inactive: bool = True,
) -> Union[DeclaredFunction[P, R], Callable[[Callable[P, R]], DeclaredFunction[P, R]]]:
    """Declare a function or actor without registering it.

    This is useful for testing or for defining functions that will be registered later.

    Args:
        func (Callable[P, R]): The function or actor to declare.
        name (str | None, optional): Filte by the name of the node. Defaults to None.
        hash (str | None, optional): Filter by the hash of the node. Defaults to None.
        optional (bool, optional): Whether the protocol is optional. Defaults to False.
        description (str | None, optional): Description of the protocol. Defaults to None.
        allow_inactive (bool, optional): Whether to allow inactive implementations. Defaults to True.

    Returns:
        WrappedFunction[P, R]: A wrapped function that can be called directly or via the actor system.
    """

    if func:
        return DeclaredProtocol(func=func[0])
    else:

        def real_decorator(
            func: Callable[P, R],
        ) -> DeclaredProtocol[P, R]:
            return DeclaredProtocol(
                func=func,
                name=name,
                hash=hash,
                optional=optional,
                description=description,
                allow_inactive=allow_inactive,
            )

        return real_decorator


T = TypeVar("T")


def agent_protocol(cls: Type[T]) -> DeclaredAgentProtocol[T]:
    """Declare an agent protocol.

    This is useful for defining agent protocols that can be registered later.

    Args:
        cls (AnyFunction): The class defining the agent protocol.

    Returns:
        AnyFunction: The same class, unmodified.
    """
    return DeclaredAgentProtocol(
        func=cls,
        name=None,
        hash=None,
        optional=False,
        description=None,
    )
