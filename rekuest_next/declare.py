"""Register a function or actor with the definition registry."""

from symtable import Class
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    ParamSpec,
    Type,
    TypeVar,
    overload,
    get_type_hints,
)
import inflection
from rekuest_next.api.schema import (
    ReturnPortInput,
    StateDependencyInput,
)
from rekuest_next.definition.dependencies import (
    build_action_dependency_input,
    build_state_dependency_input,
)
from rekuest_next.definition.define import prepare_definition
from rekuest_next.definition.define import convert_object_to_returnport
from rekuest_next.protocols import AnyFunction
from rekuest_next.structures.default import get_default_structure_registry
from rekuest_next.api.schema import (
    ActionDependencyInput,
    AgentDependencyInput,
    StateDefinitionInput,
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
        self.is_async = inspect.iscoroutinefunction(func)
        self.interface = func.__name__

    def to_dependency_input(self, key: str) -> ActionDependencyInput:
        """Convert the wrapped function to a DependencyInput."""
        return build_action_dependency_input(
            key=self.interface,
            definition=self.definition,
        )


class DeclaredAgentState(Generic[P, R]):
    """A wrapped function that calls the actor's implementation."""

    def __init__(self, stateclass: Type, agent_interface: str, key: str) -> None:
        """Initialize the wrapped function."""
        self.func = stateclass
        self.agent_interface = agent_interface
        self.key = key
        self.interface = key
        self.definition = inspect_declared_state(stateclass)

    def to_dependency_input(self, key: str) -> StateDependencyInput:
        """Convert the wrapped function to a DependencyInput."""
        return build_state_dependency_input(
            key=self.key,
            state_key=self.interface,
            definition=self.definition,
        )


Agent = TypeVar("Agent")


T = TypeVar("T")


def declare_state(cls: Type[T]) -> Type[T]:
    """Mark a class as a declared state dependency.

    Declared states are lightweight protocol-style classes used by
    :func:`declare` to describe remote state dependencies. The decorator
    sets marker attributes on the class and preserves the class unchanged.

    Args:
        cls: Class describing the exposed state fields through type annotations.

    Returns:
        The same class, annotated with rekuest state metadata.

    Examples:
        Declare a state shape for a protocol dependency::

            @declare_state
            class CameraState:
                connected: bool
                exposure_ms: float
    """
    state_cls = cls[0] if isinstance(cls, tuple) else cls
    setattr(state_cls, "__is_state__", True)
    if getattr(state_cls, "__rekuest_state__", None) is None:
        setattr(state_cls, "__rekuest_state__", state_cls.__name__)
    return state_cls


def state_dep_like(cls: Class) -> bool:
    if isinstance(cls, type) and getattr(cls, "__is_state__", None):
        return True
    return False


def inspect_declared_state(stateclass: Type[Any]) -> StateDefinitionInput:
    structure_registry = get_default_structure_registry()
    type_hints = get_type_hints(stateclass, include_extras=True)
    ports: list[ReturnPortInput] = []

    for field_name, field_type in type_hints.items():
        default = getattr(stateclass, field_name, None)
        port = convert_object_to_returnport(
            cls=field_type,
            key=field_name,
            default=default,
            registry=structure_registry,
        )
        ports.append(port)

    return StateDefinitionInput(
        ports=tuple(ports),
        name=getattr(stateclass, "__rekuest_state__", stateclass.__name__),
    )


class DeclaredAgentProtocol(Generic[Agent]):
    """A wrapped function that calls the actor's implementation."""

    def __init__(
        self,
        func: Type[Agent],
        app: str | None = None,
        min: int | None = None,
        max: int | None = None,
        version: str | None = None,
        auto_resolvable: bool = False,
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
        self.states: Dict[str, DeclaredAgentState[Any, Any]] = {}
        self.auto_resolvable = auto_resolvable
        self.min = min
        self.max = max
        self.version: str | None = version

        type_hints = get_type_hints(func)

        for dependency_key, annotation in type_hints.items():
            if dependency_key.startswith("_"):
                continue

            if state_dep_like(annotation):
                state = DeclaredAgentState(
                    annotation, self.interface, key=dependency_key
                )
                self.states[dependency_key] = state

        for dependeny_key, method in inspect.getmembers(func):
            if not dependeny_key.startswith("_") and callable(method):
                action: DeclaredAgentAction[Any, Any] = DeclaredAgentAction(
                    method, self.interface, key=dependeny_key
                )
                self.actions[dependeny_key] = action

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
            stateDemands=[
                state.to_dependency_input(key) for key, state in self.states.items()
            ],
            autoResolvable=self.auto_resolvable,
            optional=False,
            minViableInstances=self.min,
            maxViableInstances=self.max,
            version=self.version,
        )


T = TypeVar("T")


def declare(
    app: str | None = None,
    auto_resolvable: bool = False,
    min: int | None = None,
    max: int | None = None,
    version: str | None = None,
) -> Callable[[Type[T]], Type[T]]:
    """Declare a protocol that describes a remote agent dependency.

    The decorated class is inspected in two passes:

    - public methods become action demands
    - annotated attributes marked with :func:`declare_state` become state demands

    The resulting metadata is stored on the class as
    ``__rekuest__dependency__`` together with a ``to_dependency`` helper so the
    protocol can be serialized into an :class:`AgentDependencyInput` later.

    Args:
        app: Optional application namespace for dependency resolution.
        auto_resolvable: Whether any matching available agent may be assigned
            automatically.
        min: Minimum viable number of matching agents.
        max: Maximum viable number of matching agents.
        version: Optional protocol version string.

    Returns:
        A class decorator that attaches the inspected dependency metadata.

    Examples:
        Declare a protocol with action and state requirements::

            @declare_state
            class CameraState:
                connected: bool

            @declare(app="lab")
            class CameraProtocol:
                state: CameraState

                async def snap(self, exposure_ms: float) -> bytes:
                    ...
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
        setattr(the_class, "to_dependency", protocol.to_dependency_input)
        return the_class

    return real_decorator


@overload
def state_protocol(cls: Type[T]) -> Type[T]: ...


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
    if len(cls) == 1:
        return declare_state(cls[0])

    if len(cls) == 0:

        def wrapper(state_cls: Type[T]) -> Type[T]:
            return declare_state(state_cls)

        return wrapper

    raise ValueError("You can only declare one state protocol at a time.")
