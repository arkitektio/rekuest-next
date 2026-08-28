"""Register a function or actor with the definition registry."""

from typing import (
    Any,
    Generic,
    ParamSpec,
    TypeVar,
    overload,
    get_type_hints,
)
from collections.abc import Callable
from rekuest_next.api.schema import (
    ReturnPortInput,
    StateDependencyInput,
)
from rekuest_next.definition.dependencies import (
    build_action_dependency_input,
    build_state_dependency_input,
)
from rekuest_next.definition.demands import (
    ActionDemandOverride,
    StateDemandOverride,
    get_action_demand_override,
    get_state_demand_override,
    unwrap_annotated,
)
from rekuest_next.definition.define import prepare_definition
from rekuest_next.definition.define import convert_object_to_returnport
from rekuest_next.definition.utils import interface_name
from rekuest_next.protocols import AnyFunction
from rekuest_next.structures.default import get_default_structure_registry
from rekuest_next.api.schema import (
    ActionDependencyInput,
    AgentDependencyInput,
    StateDefinitionInput,
)
import inspect


P = ParamSpec("P")
R = TypeVar("R")


class DeclaredAgentAction(Generic[P, R]):
    """A wrapped function that calls the actor's implementation."""

    def __init__(
        self,
        func: AnyFunction,
        agent_interface: str,
        key: str,
        app: str | None = None,
    ) -> None:
        """Initialize the wrapped function."""
        self.func = func
        self.agent_interface = agent_interface
        self.key = key
        self.app = app
        self.override: ActionDemandOverride | None = get_action_demand_override(func)
        self.definition = prepare_definition(
            func,
            omitfirst=1,  # Omit the first parameter, which is usually `self` in agent protocols
            structure_registry=get_default_structure_registry(),
        )
        self.is_async = inspect.iscoroutinefunction(func)
        self.interface = func.__name__

    def to_dependency_input(self) -> ActionDependencyInput:
        """Convert the wrapped function to a DependencyInput.

        By default the demanded action inherits its ``app`` from the protocol's
        core app and its ``key`` from the method name. A :func:`demand` override
        on the method redirects it to another action instead.
        """
        override = self.override
        return build_action_dependency_input(
            key=self.interface,
            definition=self.definition,
            app=override.app if override and override.app is not None else self.app,
            action_key=(
                override.key
                if override and override.key is not None
                else self.interface
            ),
            version=override.version if override else None,
            hash=override.hash if override else None,
            name=override.name if override else None,
            protocols=override.protocols if override else None,
            force_arg_length=override.force_arg_length if override else None,
            force_return_length=override.force_return_length if override else None,
            match_ports=override.match_ports if override else True,
            optional=override.optional if override else False,
        )


class DeclaredAgentState:
    """A wrapped function that calls the actor's implementation."""

    def __init__(
        self,
        stateclass: type,
        agent_interface: str,
        key: str,
        app: str | None = None,
        override: "StateDemandOverride | None" = None,
    ) -> None:
        """Initialize the wrapped function."""
        self.func = stateclass
        self.agent_interface = agent_interface
        self.key = key
        self.interface = key
        self.app = app
        self.override: StateDemandOverride | None = (
            override if override is not None else get_state_demand_override(stateclass)
        )
        self.definition = inspect_declared_state(stateclass)

    def to_dependency_input(self) -> StateDependencyInput:
        """Convert the wrapped function to a DependencyInput.

        By default the demanded state inherits its ``app`` from the protocol's
        core app and its ``key`` from the attribute name. A :func:`demand_state`
        marker on the annotation redirects it to another state instead.
        """
        override = self.override
        return build_state_dependency_input(
            key=self.key,
            definition=self.definition,
            state_key=(
                override.key
                if override and override.key is not None
                else self.interface
            ),
            app=override.app if override and override.app is not None else self.app,
            hash=override.hash if override else None,
            protocols=override.protocols if override else None,
            match_ports=override.match_ports if override else True,
            optional=override.optional if override else False,
        )


Agent = TypeVar("Agent")


T = TypeVar("T")


def declare_state(cls: type[T]) -> type[T]:
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


def state_dep_like(cls: type[Any]) -> bool:
    if isinstance(cls, type) and getattr(cls, "__is_state__", None):
        return True
    return False


def inspect_declared_state(stateclass: type[Any]) -> StateDefinitionInput:
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
        func: type[Agent],
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
        self.description = description or func.__doc__
        self.allow_inactive = allow_inactive
        self.interface = interface_name(func)
        self.actions: dict[str, DeclaredAgentAction[Any, Any]] = {}
        self.states: dict[str, DeclaredAgentState] = {}
        self.auto_resolvable = auto_resolvable
        self.min = min
        self.max = max
        self.version: str | None = version

        type_hints = get_type_hints(func, include_extras=True)

        for dependency_key, annotation in type_hints.items():
            if dependency_key.startswith("_"):
                continue

            state_cls = unwrap_annotated(annotation)
            if state_dep_like(state_cls):
                state = DeclaredAgentState(
                    state_cls,
                    self.interface,
                    key=dependency_key,
                    app=self.app,
                    override=get_state_demand_override(annotation),
                )
                self.states[dependency_key] = state

        for dependeny_key, method in inspect.getmembers(func):
            if not dependeny_key.startswith("_") and callable(method):
                action: DeclaredAgentAction[Any, Any] = DeclaredAgentAction(
                    method, self.interface, key=dependeny_key, app=self.app
                )
                self.actions[dependeny_key] = action

    # Add some kwargs because we might overwrite them when looking at the params of the function annotations
    def to_dependency_input(self, key: str) -> AgentDependencyInput:
        """Convert the wrapped function to a DependencyInput."""
        return AgentDependencyInput(
            key=key,
            app=self.app,
            description=self.description or self.func.__doc__,
            actionDependencies=tuple(
                action.to_dependency_input() for action in self.actions.values()
            ),
            stateDependencies=tuple(
                state.to_dependency_input() for state in self.states.values()
            ),
            autoResolvable=self.auto_resolvable,
            optional=False,
            minViableInstances=self.min,
            maxViableInstances=self.max,
            version=self.version,
        )


T = TypeVar("T", bound=object)


def declare(
    app: str | None = None,
    auto_resolvable: bool = False,
    min: int | None = None,
    max: int | None = None,
    version: str | None = None,
) -> Callable[[type[T]], type[T]]:
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
        func: type[T],
    ) -> type[T]:  # type: ignore[valid-type]
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
def state_protocol(cls: type[T], /) -> type[T]: ...


@overload
def state_protocol() -> Callable[[type[T]], type[T]]: ...


def state_protocol(*cls: type[T]) -> type[T] | Callable[[type[T]], type[T]]:
    """Declare a state protocol; usable bare or with parentheses.

    Alias of :func:`declare_state`. The class is returned unmodified apart from
    the rekuest state markers.
    """
    if len(cls) == 1:
        return declare_state(cls[0])
    if len(cls) == 0:
        return declare_state
    raise ValueError("You can only declare one state protocol at a time.")
