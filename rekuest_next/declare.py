"""Register a function or actor with the definition registry."""

from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    ParamSpec,
    Protocol,
    Type,
    TypeVar,
    Union,
    overload,
    runtime_checkable,
)
from unicodedata import name
from unittest.mock import seal
import inflection
from rekuest_next.api.schema import ActionKind, ArgPortInput, ReturnPortInput
from rekuest_next.remote import call, call_dependency, iterate
from rekuest_next.actors.vars import get_current_assignation_helper
from rekuest_next.definition.define import prepare_definition
from rekuest_next.definition.hash import hash_definition
from rekuest_next.protocols import AnyFunction
from rekuest_next.structures.default import get_default_structure_registry
from rekuest_next.api.schema import (
    ActionDependencyInput,
    Implementation,
    PortMatchInput,
    get_implementation,
    AgentDependencyInput,
)
import inspect
from typing import TYPE_CHECKING


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


def port_to_match(index: int, port: ArgPortInput) -> PortMatchInput:
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


def returnport_to_match(index: int, port: ReturnPortInput) -> PortMatchInput:
    return PortMatchInput(
        at=index,
        key=port.key,
        identifier=port.identifier,
        kind=port.kind,
        nullable=port.nullable,
        children=[
            returnport_to_match(index, child)
            for index, child in enumerate(port.children or [])
        ]
        if port.children
        else None,
    )


class DeclaredAgentAction(Generic[P, R]):
    """A wrapped function that calls the actor's implementation."""

    def __init__(self, func: AnyFunction, agent_interface: str, key: str) -> None:
        """Initialize the wrapped function."""
        self.func = func
        self.agent_interface = agent_interface
        self.key = key
        self.definition = prepare_definition(
            func,
            omitfirst=True,  # Omit the first parameter, which is usually `self` in agent protocols
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
                key,
                self.interface,
                *args,
                parent=helper.assignment,
                **kwargs,
            )
        elif self.definition.kind == ActionKind.GENERATOR:
            raise NotImplementedError(
                "Generator actions are not supported in agent protocols."
            )
        else:
            raise Exception(
                f"Cannot call implementation of kind {self.definition.kind}"
            )

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """ "Call the wrapped function directly if not within an assignation."""
        return self.call(*args, **kwargs)

    def to_dependency_input(self, key: str) -> ActionDependencyInput:
        """Convert the wrapped function to a DependencyInput."""

        arg_matches: list[PortMatchInput] = []
        return_matches: list[PortMatchInput] = []

        for index, arg in enumerate(self.definition.args):
            arg_matches.append(port_to_match(index, arg))

        for index, ret in enumerate(self.definition.returns):
            return_matches.append(returnport_to_match(index, ret))

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
        app: str | None = None,
        min: int | None = None,
        max: int | None = None,
        version: str | None = None,
        auto_resolvable: bool = True,
        description: str | None = None,
        allow_inactive: bool = True,
    ) -> None:
        """Initialize the wrapped function."""
        self.func = func
        self.app = app
        self.hash = hash
        self.description = description or func.__doc__
        self.allow_inactive = allow_inactive
        self.interface = interface_name(func)
        self.actions: Dict[str, DeclaredAgentAction[Any, Any]] = {}
        self.auto_resolvable = auto_resolvable
        self.min = min
        self.max = max
        self.version: str | None = version

        for dependeny_key, method in inspect.getmembers(func):
            if not dependeny_key.startswith("_") and callable(method):
                action: DeclaredAgentAction[Any, Any] = DeclaredAgentAction(
                    method, self.interface, key=dependeny_key
                )
                self.actions[dependeny_key] = action
                setattr(self, dependeny_key, action)

    # Add some kwargs because we might overwrite them when looking at the params of the function annotations
    def to_dependency_input(self, key: str) -> AgentDependencyInput:
        """Convert the wrapped function to a DependencyInput."""
        return AgentDependencyInput(
            key=key,
            app=self.app,
            description=self.description or self.func.__doc__,
            actionDemands=[
                action.to_dependency_input(key) for key, action in self.actions.items()
            ],
            autoResolvable=self.auto_resolvable,
            optional=False,
            minViableInstances=self.min,
            maxViableInstances=self.max,
            version=self.version,
        )


T = TypeVar("T")


@runtime_checkable
class Resolvable(Protocol):
    """A protocol for resolvable dependencies."""

    def resolve(self, **kwargs: Any) -> Any:
        """Resolve the dependency."""
        ...


def agent_protocol(
    app: str | None = None,
    auto_resolvable: bool = True,
    min: int | None = None,
    max: int | None = None,
    version: str | None = None,
) -> Callable[[Type[T]], Type[T]]:
    """Declare an agent protocol.

    This is useful for defining agent protocols that can be registered later.

    Args:
        cls (AnyFunction): The class defining the agent protocol.
        app (str): The application name.
        version (str | None, optional): The version of the agent protocol. Defaults to None.
        auto_resolvable (bool, optional): Whether we can autoassign any available agent that matches this protocol. Defaults to False. (You should set this to False if the agent is somewhat "physical" or robotic, i.e it matters that not the robot with a knife to a kittens throat is called)
        min (int | None, optional): The minimum number of agents that can be assigned to this protocol. Defaults to None.
        max (int | None, optional): The maximum number of agents that can be assigned to this protocol. Defaults to None.
    Returns:
        AnyFunction: The same class, unmodified.
    """

    def real_decorator(
        func: Type[T],
    ) -> Type[T]:  # type: ignore[valid-type]
        the_class = func
        protocol = DeclaredAgentProtocol(
            func=the_class,
            app=app,
            auto_resolvable=auto_resolvable,
            min=min,
            max=max,
            version=version,
        )
        setattr(the_class, "__rekuest__dependency__", protocol)
        return the_class

    return real_decorator


@overload
def state_protocol(func: Type[T]) -> Type[T]: ...


@overload
def state_protocol(
    *,
    app: str | None = None,
    version: str | None = None,
    min: int | None = None,
    max: int | None = None,
) -> Callable[[Type[T]], Type[T]]: ...


def state_protocol(
    *cls: Type[T],
    app: str | None = None,
    version: str | None = None,
    min: int | None = None,
    max: int | None = None,
) -> Type[T]:
    """Declare an state protocol.

    This is useful for defining state protocols that can be registered later.

    Args:
        cls (AnyFunction): The class defining the agent protocol.
        app (str): The application name.
        version (str | None, optional): The version of the agent protocol. Defaults to None.

    Returns:
        AnyFunction: The same class, unmodified.
    """
    return cls


declare = agent_protocol
dependency = agent_protocol
