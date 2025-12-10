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
from rekuest_next.coercible_types import DependencyCoercible
from rekuest_next.remote import acall, call
from rekuest_next.actors.actify import reactify
from rekuest_next.actors.sync import SyncGroup
from rekuest_next.actors.types import Actifier, ActorBuilder, OnProvide, OnUnprovide
from rekuest_next.actors.vars import get_current_assignation_helper
from rekuest_next.definition.define import AssignWidgetMap
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
    amy_implementation_at,
    get_implementation,
    EffectInput,
    ImplementationInput,
    ValidatorInput,
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
        """ "Call the wrapped function directly if not within an assignation."""
        try:
            helper = get_current_assignation_helper()

            try:
                dependency = helper.get_dependency(
                    self.interface,
                )
            except KeyError:
                dependency = None  # type: ignore
                logger.debug(
                    "No dependency found for interface %s, but registered locally calling it directly.",
                    self.interface,
                )  # TODO: Figure out if we want this behavior
                return self.func(*args, **kwargs)

            implementation = get_implementation(dependency)
            return call(implementation, *args, parent=helper.assignment, **kwargs)
        except NotWithinAnAssignationError:
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
    definition_registry: DefinitionRegistry,
    interface: Optional[str] = None,
    name: Optional[str] = None,
    actifier: Actifier = reactify,
    description: Optional[str] = None,
    dependencies: Optional[List[DependencyCoercible]] = None,
    port_groups: Optional[List[PortGroupInput]] = None,
    validators: Optional[Dict[str, List[ValidatorInput]]] = None,
    collections: Optional[List[str]] = None,
    is_test_for: Optional[List[str]] = None,
    logo: Optional[str] = None,
    widgets: Optional[AssignWidgetMap] = None,
    effects: Optional[Dict[str, List[EffectInput]]] = None,
    interfaces: Optional[List[str]] = None,
    on_provide: Optional[OnProvide] = None,
    on_unprovide: Optional[OnUnprovide] = None,
    dynamic: bool = False,
    in_process: bool = False,
    sync: Optional[SyncGroup] = None,
    stateful: bool = False,
) -> Tuple[DefinitionInput, ActorBuilder]:
    """Register a function or actor with the provided definition registry.

    This function wraps a callable or actor into an ActorBuilder and registers it with a
    DefinitionRegistry instance, using an optionally provided or inferred interface name.

    Args:
        function_or_actor (AnyFunction): A function or actor to be registered.
        structure_registry (StructureRegistry): The registry used for structuring inputs.
        definition_registry (DefinitionRegistry): The registry where definitions are stored.
        interface (Optional[str], optional): Interface name. Inferred if not provided.
        name (Optional[str], optional): Optional display name.
        actifier (Actifier, optional): Callable converting functions to actors. Defaults to reactify.
        dependencies (Optional[List[DependencyInput]], optional): External dependencies.
        port_groups (Optional[List[PortGroupInput]], optional): Port group specifications.
        validators (Optional[Dict[str, List[ValidatorInput]]], optional): Validator mappings.
        collections (Optional[List[str]], optional): Collection groupings.
        is_test_for (Optional[List[str]], optional): Interfaces this definition tests.
        logo (Optional[str], optional): Optional logo URL.
        widgets (Optional[AssignWidgetMap], optional): Widget mappings.
        effects (Optional[Dict[str, List[EffectInput]]], optional): Side-effect configurations.
        interfaces (Optional[List[str]], optional): Interfaces implemented by this actor.
        on_provide (Optional[OnProvide], optional): Provision hook.
        on_unprovide (Optional[OnUnprovide], optional): Unprovision hook.
        dynamic (bool, optional): Whether the definition is dynamically changeable.
        in_process (bool, optional): Whether to run in the same process.
        sync (Optional[SyncGroup], optional): Synchronization group, if any.
        stateful (bool, optional): Indicates whether the actor is stateful.

    Returns:
        Tuple[DefinitionInput, ActorBuilder]: Registered definition and its actor builder.
    """
    interface = interface or interface_name(function_or_actor)

    definition, actor_builder = actifier(
        function_or_actor,
        structure_registry,
        on_provide=on_provide,
        on_unprovide=on_unprovide,
        widgets=widgets,
        is_test_for=is_test_for,
        collections=collections,
        logo=logo,
        name=name,
        description=description,
        stateful=stateful,
        port_groups=port_groups,
        effects=effects,
        sync=sync,
        validators=validators,
        interfaces=interfaces,
        in_process=in_process,
    )

    definition_registry.register_at_interface(
        interface,
        ImplementationInput(
            interface=interface,
            definition=definition,
            dependencies=tuple(
                [
                    x
                    if isinstance(x, ActionDependencyInput)
                    else x.to_dependency_input()
                    for x in (dependencies or [])
                ]
            ),
            logo=logo,
            dynamic=dynamic,
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
        definition_registry (Optional[DefinitionRegistry], optional): Custom definition registry instance.
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
    dependencies: Optional[List[DependencyCoercible]] = None,
    interfaces: Optional[List[str]] = None,
    collections: Optional[List[str]] = None,
    port_groups: Optional[List[PortGroupInput]] = None,
    effects: Optional[Dict[str, List[EffectInput]]] = None,
    is_test_for: Optional[List[str]] = None,
    logo: Optional[str] = None,
    on_provide: Optional[OnProvide] = None,
    on_unprovide: Optional[OnUnprovide] = None,
    validators: Optional[Dict[str, List[ValidatorInput]]] = None,
    structure_registry: Optional[StructureRegistry] = None,
    definition_registry: Optional[DefinitionRegistry] = None,
    in_process: bool = False,
    dynamic: bool = False,
    sync: Optional[SyncGroup] = None,
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
        definition_registry (Optional[DefinitionRegistry], optional): Custom definition registry instance.
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
    dependencies: Optional[List[DependencyCoercible]] = None,
    interfaces: Optional[List[str]] = None,
    collections: Optional[List[str]] = None,
    port_groups: Optional[List[PortGroupInput]] = None,
    effects: Optional[Dict[str, List[EffectInput]]] = None,
    is_test_for: Optional[List[str]] = None,
    logo: Optional[str] = None,
    on_provide: Optional[OnProvide] = None,
    on_unprovide: Optional[OnUnprovide] = None,
    validators: Optional[Dict[str, List[ValidatorInput]]] = None,
    structure_registry: Optional[StructureRegistry] = None,
    definition_registry: Optional[DefinitionRegistry] = None,
    in_process: bool = False,
    dynamic: bool = False,
    sync: Optional[SyncGroup] = None,
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
        definition_registry (Optional[DefinitionRegistry], optional): Overrides default definition registry.
        in_process (bool, optional): Execute actor in the current process.
        dynamic (bool, optional): Enables dynamic redefinition.
        sync (Optional[SyncGroup], optional): Synchronization group instance.

    Returns:
        Union[T, Callable[[T], T]]: The registered function or a decorator.
    """
    definition_registry = definition_registry or get_default_definition_registry()
    structure_registry = structure_registry or get_default_structure_registry()

    if len(func) > 1:
        raise ValueError("You can only register one function or actor at a time.")
    if len(func) == 1:
        function_or_actor = func[0]

        definition, _ = register_func(
            function_or_actor,
            name=name,
            description=description,
            structure_registry=structure_registry,
            definition_registry=definition_registry,
            dependencies=dependencies,
            validators=validators,
            actifier=actifier,
            stateful=stateful,
            interface=interface,
            is_test_for=is_test_for,
            widgets=widgets,
            logo=logo,
            effects=effects,
            collections=collections,
            interfaces=interfaces,
            on_provide=on_provide,
            on_unprovide=on_unprovide,
            port_groups=port_groups,
            in_process=in_process,
            dynamic=dynamic,
            sync=sync,
        )

        setattr(function_or_actor, "__definition__", definition)
        setattr(function_or_actor, "__definition_hash__", hash_definition(definition))
        setattr(
            function_or_actor,
            "__interface__",
            interface or interface_name(function_or_actor),
        )

        return WrappedFunction(
            function_or_actor,
            interface or interface_name(function_or_actor),
            definition,
        )

    else:

        def real_decorator(function_or_actor: Callable[P, R]) -> WrappedFunction[P, R]:
            definition, _ = register_func(
                function_or_actor,
                name=name,
                description=description,
                structure_registry=structure_registry,
                definition_registry=definition_registry,
                actifier=actifier,
                interface=interface,
                validators=validators,
                stateful=stateful,
                dependencies=dependencies,
                is_test_for=is_test_for,
                widgets=widgets,
                effects=effects,
                collections=collections,
                interfaces=interfaces,
                on_provide=on_provide,
                logo=logo,
                on_unprovide=on_unprovide,
                port_groups=port_groups,
                dynamic=dynamic,
                in_process=in_process,
                sync=sync,
            )

            setattr(function_or_actor, "__definition__", definition)
            setattr(
                function_or_actor, "__definition_hash__", hash_definition(definition)
            )
            setattr(
                function_or_actor,
                "__interface__",
                interface or interface_name(function_or_actor),
            )

            return WrappedFunction(
                function_or_actor,
                interface or interface_name(function_or_actor),
                definition,
            )

        return cast(Callable[[T], T], real_decorator)  # type: ignore


def register_test(
    test_function: AnyFunction,
    structure_registry: Optional[StructureRegistry] = None,
    definition_registry: Optional[DefinitionRegistry] = None,
) -> WrappedFunction[..., Any]:
    """Register a test function for specified interfaces.

    This function wraps a test function into an actor and registers it as a test
    for the provided interfaces in the definition registry.

    Args:
        test_function (AnyFunction): The test function to register.
        tested_interfaces (List[str]): List of interfaces that this function tests.
        structure_registry (Optional[StructureRegistry], optional): Custom structure registry instance.
        definition_registry (Optional[DefinitionRegistry], optional): Custom definition registry instance.

    Returns:
        WrappedFunction[..., Any]: The registered test function wrapped.
    """
    return register(
        dependencies=[test_function],
        test_for=test_function,
        structure_registry=structure_registry,
        definition_registry=definition_registry,
    )
