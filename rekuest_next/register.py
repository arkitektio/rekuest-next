"""Register a function or actor with the definition registry."""

from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Literal,
    Optional,
    ParamSpec,
    Tuple,
    TypeVar,
    Union,
    overload,
    cast,
)
import inflection

if TYPE_CHECKING:
    from rekuest_next.app import AppRegistry
from rekuest_next.coercible_types import (
    OptimisticCoercible,
)
from rekuest_next.remote import acall, call
from rekuest_next.actors.actify import reactify
from rekuest_next.actors.types import Actifier, ActorBuilder, RegisterConfig
from rekuest_next.actors.vars import get_current_task_helper
from rekuest_next.definition.define import (
    dependency_to_dependency_input,
)
from rekuest_next.definition.dependencies import build_action_dependency_input
from rekuest_next.definition.hash import hash_definition
from rekuest_next.protocols import AnyFunction
from rekuest_next.structures.default import get_default_structure_registry
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.api.schema import (
    AssignWidgetInput,
    DefinitionInput,
    ActionDependencyInput,
    TrackInput,
    PortGroupInput,
    amy_implementation_at,
    EffectInput,
    ImplementationInput,
    ValidatorInput,
    AgentDependencyInput,
    OptimisticInput,
    my_implementation_at,
)
import logging


logger = logging.getLogger(__name__)


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


class WrappedFunction(Generic[P, R]):
    """A wrapped function that calls the actor's implementation."""

    def __init__(
        self, func: Callable[P, R], interface: str, definition: DefinitionInput
    ) -> None:
        """Initialize the wrapped function."""
        self.func = func
        self.interface = interface
        self.definition = definition
        self.hash = hash_definition(definition)

    def call(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """ "Call the actor's implementation."""
        helper = get_current_task_helper()
        implementation = my_implementation_at(self.interface)

        return call(
            implementation,
            *args,
            parent=helper.assignment,
            **cast("Dict[str, Any]", kwargs),
        )

    async def acall(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """ "Asynchronously call the actor's implementation."""
        helper = get_current_task_helper()
        implementation = await amy_implementation_at(self.interface)

        return await acall(
            implementation,
            *args,
            parent=helper.assignment,
            **cast("Dict[str, Any]", kwargs),
        )

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """Call the actor's implementation."""
        return self.func(*args, **kwargs)

    def to_dependency_input(self) -> ActionDependencyInput:
        """Convert the wrapped function to a DependencyInput."""
        return build_action_dependency_input(
            key=self.interface,
            definition=self.definition,
            optional=False,
        )


def register_func(
    function_or_actor: AnyFunction,
    structure_registry: StructureRegistry,
    implementation_registry: "AppRegistry",
    config: Optional[RegisterConfig] = None,
    *,
    actifier: Actifier = reactify,
) -> Tuple[DefinitionInput, ActorBuilder]:
    """Register a function or actor with the provided app registry.

    This function wraps a callable or actor into an ActorBuilder and registers it
    with an AppRegistry instance, at ``config.interface`` or an interface name
    inferred from the function name.

    Args:
        function_or_actor (AnyFunction): A function or actor to be registered.
        structure_registry (StructureRegistry): The registry used for structuring inputs.
        implementation_registry (AppRegistry): The registry where implementations are stored.
        config (Optional[RegisterConfig], optional): Bundled registration options.
            Defaults to an empty ``RegisterConfig``.
        actifier (Actifier, optional): Callable converting functions to actors. Defaults to reactify.

    Returns:
        Tuple[DefinitionInput, ActorBuilder]: Registered definition and its actor builder.
    """
    config = config or RegisterConfig()
    interface = config.interface or interface_name(function_or_actor)

    definition, implementation_details, actor_builder = actifier(
        function_or_actor,
        structure_registry,
        config,
    )

    dependencies: list[AgentDependencyInput] = []
    for (
        key,
        dependency,
    ) in implementation_details.dependency_variables.dependency_variables.items():
        dependencies.append(dependency_to_dependency_input(key, dependency))

    optimistics: list[OptimisticInput] = [
        optimistic
        if isinstance(optimistic, OptimisticInput)
        else optimistic.to_optimistic_input()
        for optimistic in (config.optimistics or [])
    ]

    implementation_registry.register_at_interface(
        interface,
        ImplementationInput(
            interface=interface,
            definition=definition,
            logo=config.logo,
            dynamic=config.dynamic,
            locks=tuple(implementation_details.locks or []),
            optimistics=tuple(optimistics),
            dependencies=tuple(dependencies),
            tracks=tuple(implementation_details.tracks or []),
            needs_token=True,  # TODO: Make this configurable in the future, but for now, we want to ensure that all actors require tokens for security reasons.
            manipulates=tuple(implementation_details.manipulates or []),
        ),
        actor_builder,
    )

    return definition, actor_builder


T = TypeVar("T", bound=AnyFunction)


@overload
def register(func: Callable[P, R]) -> WrappedFunction[P, R]:
    """Register a function or actor directly: ``@register``."""
    ...


@overload
def register(
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    actifier: Actifier = reactify,
    interface: Optional[str] = None,
    stateful: bool = False,
    widgets: Optional[Dict[str, AssignWidgetInput]] = None,
    interfaces: Optional[List[str]] = None,
    collections: Optional[List[str]] = None,
    port_groups: Optional[List[PortGroupInput]] = None,
    effects: Optional[Dict[str, List[EffectInput]]] = None,
    is_test_for: Optional[List[str]] = None,
    logo: Optional[str] = None,
    validators: Optional[Dict[str, List[ValidatorInput]]] = None,
    structure_registry: Optional[StructureRegistry] = None,
    implementation_registry: Optional["AppRegistry"] = None,
    optimistics: Optional[List[OptimisticCoercible]] = None,
    in_process: bool = False,
    tracks: Optional[List[TrackInput]] = None,
    dynamic: bool = False,
    locks: Optional[List[str]] = None,
    concurrency: Literal["parallel", "serial"] = "serial",
    version: Optional[str] = None,
) -> Callable[[Callable[P, R]], WrappedFunction[P, R]]:
    """Register a function or actor with configuration: ``@register(...)``."""
    ...


def register(  # type: ignore[valid-type]
    *func: Callable[P, R],
    name: Optional[str] = None,
    actifier: Actifier = reactify,
    interface: Optional[str] = None,
    stateful: bool = False,
    description: Optional[str] = None,
    widgets: Optional[Dict[str, AssignWidgetInput]] = None,
    interfaces: Optional[List[str]] = None,
    collections: Optional[List[str]] = None,
    port_groups: Optional[List[PortGroupInput]] = None,
    effects: Optional[Dict[str, List[EffectInput]]] = None,
    is_test_for: Optional[List[str]] = None,
    logo: Optional[str] = None,
    optimistics: Optional[List[OptimisticCoercible]] = None,
    validators: Optional[Dict[str, List[ValidatorInput]]] = None,
    structure_registry: Optional[StructureRegistry] = None,
    tracks: Optional[List[TrackInput]] = None,
    implementation_registry: Optional["AppRegistry"] = None,
    in_process: bool = False,
    dynamic: bool = False,
    locks: Optional[List[str]] = None,
    concurrency: Literal["parallel", "serial"] = "serial",
    version: Optional[str] = None,
) -> Union[WrappedFunction[P, R], Callable[[Callable[P, R]], WrappedFunction[P, R]]]:
    """Register a function or actor with an app registry.

    Serves as both a bare decorator and a configurable decorator. All keyword
    arguments are bundled into a single :class:`RegisterConfig` that is threaded
    through ``register_func`` and the actifier.

    Use this as:
        @register
        def my_function(...): ...

    Or with arguments:
        @register(interface="custom_interface", widgets={...})
        def my_function(...): ...

    Args:
        *func: Function to register when used as a bare decorator.
        name (Optional[str]): Display name. Defaults to the function name.
        description (Optional[str]): Description. Defaults to the docstring.
        actifier (Actifier): Converts the callable into an actor builder.
            Defaults to :func:`reactify`.
        interface (Optional[str]): Interface name. Inferred from the function
            name if not provided.
        stateful (bool): Mark the definition stateful (auto-set when the
            function uses state variables).
        widgets (Optional[Dict[str, AssignWidgetInput]]): Widgets per argument.
        interfaces (Optional[List[str]]): Additional interfaces implemented.
        collections (Optional[List[str]]): Organizational groupings.
        port_groups (Optional[List[PortGroupInput]]): Port group assignments.
        effects (Optional[Dict[str, List[EffectInput]]]): Effects per port.
        is_test_for (Optional[List[str]]): Interfaces this function tests.
        logo (Optional[str]): URL or identifier of the action's logo.
        validators (Optional[Dict[str, List[ValidatorInput]]]): Input validation
            rules per argument.
        structure_registry (Optional[StructureRegistry]): Overrides the default
            structure registry.
        implementation_registry (Optional[AppRegistry]): Overrides the default
            app registry.
        optimistics (Optional[List[OptimisticCoercible]]): Optimistic outputs.
        in_process (bool): Run the actor in the event loop instead of a thread.
        tracks (Optional[List[TrackInput]]): Tracks the implementation follows.
        dynamic (bool): Whether the definition may change dynamically.
        locks (Optional[List[str]]): Resource locks held during assignment
            (auto-inferred from state/context locks when omitted).
        concurrency (Literal["parallel", "serial"]): Whether assignments to the
            actor may run concurrently ("parallel") or one at a time
            ("serial", the default).
        version (Optional[str]): Version of the definition.

    Returns:
        The wrapped function, or a decorator producing it.
    """
    from rekuest_next.app import get_default_app_registry

    implementation_registry = implementation_registry or get_default_app_registry()
    structure_registry = structure_registry or get_default_structure_registry()

    config = RegisterConfig(
        name=name,
        description=description,
        interface=interface,
        widgets=widgets,
        effects=effects,
        validators=validators,
        collections=collections,
        port_groups=port_groups,
        interfaces=interfaces,
        is_test_for=is_test_for,
        logo=logo,
        stateful=stateful,
        version=version,
        dynamic=dynamic,
        optimistics=optimistics,
        locks=locks,
        concurrency=concurrency,
        tracks=tracks,
        in_process=in_process,
    )

    def _register(function_or_actor: Callable[P, R]) -> WrappedFunction[P, R]:
        any_function = cast(AnyFunction, function_or_actor)
        iface = config.interface or interface_name(any_function)

        definition, _ = register_func(
            any_function,
            structure_registry,
            implementation_registry,
            config,
            actifier=actifier,
        )

        target = getattr(function_or_actor, "__func__", function_or_actor)
        setattr(target, "__definition__", definition)
        setattr(target, "__definition_hash__", hash_definition(definition))
        setattr(target, "__interface__", iface)

        return WrappedFunction(function_or_actor, iface, definition)

    if len(func) > 1:
        raise ValueError("You can only register one function or actor at a time.")
    if len(func) == 1:
        return _register(func[0])

    return cast(Callable[[T], T], _register)  # type: ignore
