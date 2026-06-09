"""Register a function or actor with the definition registry."""

from typing import (
    TYPE_CHECKING,
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

if TYPE_CHECKING:
    from rekuest_next.app import AppRegistry
from rekuest_next.coercible_types import (
    OptimisticCoercible,
)
from rekuest_next.remote import acall, call
from rekuest_next.actors.actify import reactify
from rekuest_next.actors.sync import SyncGroup
from rekuest_next.actors.types import Actifier, ActorBuilder, RegisterConfig
from rekuest_next.actors.vars import get_current_assignation_helper
from rekuest_next.definition.define import (
    dependency_to_dependency_input,
)
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
        self, func: AnyFunction, interface: str, definition: DefinitionInput
    ) -> None:
        """Initialize the wrapped function."""
        self.func = func
        self.interface = interface
        self.definition = definition
        self.hash = hash_definition(definition)

    def call(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """ "Call the actor's implementation."""
        helper = get_current_assignation_helper()
        implementation = my_implementation_at(
            helper.actor.agent.instance_id, self.interface
        )

        return call(implementation, *args, parent=helper.assignment, **kwargs)

    async def acall(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """ "Asynchronously call the actor's implementation."""
        helper = get_current_assignation_helper()
        implementation = await amy_implementation_at(
            helper.actor.agent.instance_id, self.interface
        )

        return await acall(implementation, *args, parent=helper.assignment, **kwargs)

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """Call the actor's implementation."""
        return self.func(*args, **kwargs)

    def to_dependency_input(self) -> ActionDependencyInput:
        """Convert the wrapped function to a DependencyInput."""
        return ActionDependencyInput(
            key=self.interface,
            optional=False,
            hash=hash_definition(self.definition),
        )


def register_func(
    function_or_actor: AnyFunction,
    structure_registry: StructureRegistry,
    implementation_registry: "AppRegistry",
    config: Optional[RegisterConfig] = None,
    *,
    interface: Optional[str] = None,
    actifier: Actifier = reactify,
) -> Tuple[DefinitionInput, ActorBuilder]:
    """Register a function or actor with the provided definition registry.

    This function wraps a callable or actor into an ActorBuilder and registers it with a
    DefinitionRegistry instance, using an optionally provided or inferred interface name.

    Args:
        function_or_actor (AnyFunction): A function or actor to be registered.
        structure_registry (StructureRegistry): The registry used for structuring inputs.
        implementation_registry (AppRegistry): The registry where implementations are stored.
        config (Optional[RegisterConfig], optional): Bundled registration options.
            Defaults to an empty ``RegisterConfig``.
        interface (Optional[str], optional): Interface name. Inferred if not provided.
        actifier (Actifier, optional): Callable converting functions to actors. Defaults to reactify.

    Returns:
        Tuple[DefinitionInput, ActorBuilder]: Registered definition and its actor builder.
    """
    config = config or RegisterConfig()
    interface = interface or interface_name(function_or_actor)

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

    implementation_registry.register_at_interface(
        interface,
        ImplementationInput(
            interface=interface,
            definition=definition,
            logo=config.logo,
            dynamic=config.dynamic,
            locks=implementation_details.locks or [],
            optimistics=config.optimistics if config.optimistics else [],
            dependencies=dependencies,
            tracks=implementation_details.tracks or [],
            manipulates=implementation_details.manipulates or [],
        ),
        actor_builder,
    )

    return definition, actor_builder


T = TypeVar("T", bound=AnyFunction)


@overload
def register(func: Callable[P, R]) -> WrappedFunction[P, R]:
    """Register a function or actor with optional configuration parameters.

    This overload supports usage of `@register(...)` as a configurable decorator.

    Args:
        func (T): Function to register.
        actifier (Actifier, optional): Function to wrap callables into actors.
        interface (Optional[str], optional): Interface name override.
        stateful (bool, optional): Whether the actor maintains internal state.
        widgets (Optional[Dict[str, AssignWidgetInput]], optional): Mapping of parameter names to widgets.
        dependencies (Optional[List[DependencyInput]], optional): List of external dependencies.
        interfaces (Optional[List[str]], optional): Additional interfaces implemented.
        collections (Optional[List[str]], optional): Groupings for organizational purposes.
        port_groups (Optional[List[PortGroupInput]], optional): Port group assignments.
        effects (Optional[Dict[str, List[EffectInput]]], optional): Mapping of effects per port.
        is_test_for (Optional[List[str]], optional): Interfaces this function serves as a test for.
        logo (Optional[str], optional): URL or identifier for the actor's logo.
        on_provide (Optional[OnProvide], optional): Hook triggered when actor is provided.
        on_unprovide (Optional[OnUnprovide], optional): Hook triggered when actor is unprovided.
        validators (Optional[Dict[str, List[ValidatorInput]]], optional): Input validation rules.
        structure_registry (Optional[StructureRegistry], optional): Custom structure registry instance.
        implementation_registry (Optional[DefinitionRegistry], optional): Custom implementation registry instance.
        in_process (bool, optional): Execute actor in the same process.
        dynamic (bool, optional): Whether the actor definition is subject to change dynamically.
        sync (Optional[SyncGroup], optional): Optional synchronization group.

    Returns:
        Callable[[T], T]: A decorator that registers the given function or actor.
    """
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
    sync: Optional[SyncGroup] = None,
    locks: Optional[List[str]] = None,
    version: Optional[str] = None,
) -> Callable[[Callable[P, R]], WrappedFunction[P, R]]:
    """Register a function or actor with optional configuration parameters.

    This overload supports usage of `@register(...)` as a configurable decorator.

    Args:
        actifier (Actifier, optional): Function to wrap callables into actors.
        interface (Optional[str], optional): Interface name override.
        stateful (bool, optional): Whether the actor maintains internal state.
        widgets (Optional[Dict[str, AssignWidgetInput]], optional): Mapping of parameter names to widgets.
        dependencies (Optional[List[DependencyInput]], optional): List of external dependencies.
        interfaces (Optional[List[str]], optional): Additional interfaces implemented.
        collections (Optional[List[str]], optional): Groupings for organizational purposes.
        port_groups (Optional[List[PortGroupInput]], optional): Port group assignments.
        effects (Optional[Dict[str, List[EffectInput]]], optional): Mapping of effects per port.
        is_test_for (Optional[List[str]], optional): Interfaces this function serves as a test for.
        logo (Optional[str], optional): URL or identifier for the actor's logo.
        on_provide (Optional[OnProvide], optional): Hook triggered when actor is provided.
        on_unprovide (Optional[OnUnprovide], optional): Hook triggered when actor is unprovided.
        validators (Optional[Dict[str, List[ValidatorInput]]], optional): Input validation rules.
        structure_registry (Optional[StructureRegistry], optional): Custom structure registry instance.
        implementation_registry (Optional[DefinitionRegistry], optional): Custom implementation registry instance.
        in_process (bool, optional): Execute actor in the same process.
        dynamic (bool, optional): Whether the actor definition is subject to change dynamically.
        sync (Optional[SyncGroup], optional): Optional synchronization group.

    Returns:
        Callable[[T], T]: A decorator that registers the given function or actor.
    """
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
    version: Optional[str] = None,
) -> Union[WrappedFunction[P, R], Callable[[Callable[P, R]], WrappedFunction[P, R]]]:
    """Register a function or actor to the default definition and structure registries.

    This function serves as both a decorator and a direct-call function to register
    actors or callables. It supports detailed customization of the registration
    process including dependency tracking, custom widgets, interface annotations,
    validation, and lifecycle hooks.

    Use this as:
        @register
        def my_function(...): ...

    Or with arguments:
        @register(interface="custom_interface", dependencies=[...])
        def my_function(...): ...

    Or as a direct call:
        register(my_function, interface="custom_interface", ...)

    Args:
        *func (T): Function to register if using direct-call mode.
        actifier (Actifier, optional): Function to transform a callable into an actor.
        interface (Optional[str], optional): Interface name; inferred from function if not provided.
        stateful (bool, optional): Whether the actor maintains internal state.
        widgets (Optional[Dict[str, AssignWidgetInput]], optional): Optional widget configurations.
        dependencies (Optional[List[DependencyInput]], optional): External dependencies required.
        interfaces (Optional[List[str]], optional): Interfaces this actor complies with.
        collections (Optional[List[str]], optional): Groupings for organizing definitions.
        port_groups (Optional[List[PortGroupInput]], optional): Input/output port groupings.
        effects (Optional[Dict[str, List[EffectInput]]], optional): Side-effects mapping.
        is_test_for (Optional[List[str]], optional): Indicates the actor is a test for given interfaces.
        logo (Optional[str], optional): Optional logo or image identifier.
        on_provide (Optional[OnProvide], optional): Async hook called on provisioning.
        on_unprovide (Optional[OnUnprovide], optional): Async hook called on unprovisioning.
        validators (Optional[Dict[str, List[ValidatorInput]]], optional): Validation configuration.
        structure_registry (Optional[StructureRegistry], optional): Overrides default structure registry.
        implementation_registry (Optional[DefinitionRegistry], optional): Overrides default implementation registry.
        in_process (bool, optional): Execute actor in the current process.
        dynamic (bool, optional): Enables dynamic redefinition.
        locks (Optional[List[str]], optional): List of resource locks.

    Returns:
        Union[T, Callable[[T], T]]: The registered function or a decorator.
    """
    from rekuest_next.app import get_default_app_registry

    implementation_registry = implementation_registry or get_default_app_registry()
    structure_registry = structure_registry or get_default_structure_registry()

    config = RegisterConfig(
        name=name,
        description=description,
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
        tracks=tracks,
        in_process=in_process,
    )

    def _register(function_or_actor: Callable[P, R]) -> WrappedFunction[P, R]:
        definition, _ = register_func(
            function_or_actor,
            structure_registry,
            implementation_registry,
            config,
            interface=interface,
            actifier=actifier,
        )

        target = getattr(function_or_actor, "__func__", function_or_actor)
        setattr(target, "__definition__", definition)
        setattr(target, "__definition_hash__", hash_definition(definition))
        setattr(
            target,
            "__interface__",
            interface or interface_name(function_or_actor),
        )

        return WrappedFunction(
            function_or_actor,
            interface or interface_name(function_or_actor),
            definition,
        )

    if len(func) > 1:
        raise ValueError("You can only register one function or actor at a time.")
    if len(func) == 1:
        return _register(func[0])

    return cast(Callable[[T], T], _register)  # type: ignore


action = register
