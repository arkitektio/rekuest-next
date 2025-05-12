"""Register a function or actor with the definition registry"""

from rekuest_next.actors.sync import SyncGroup
from rekuest_next.actors.types import Actifier, ActorBuilder, OnUnprovide, OnProvide
from rekuest_next.definition.define import AssignWidgetMap
from rekuest_next.definition.hash import hash_definition
from rekuest_next.protocols import AnyFunction
from rekuest_next.structures.registry import (
    StructureRegistry,
)
from rekuest_next.structures.default import (
    get_default_structure_registry,
)
from rekuest_next.definition.registry import (
    DefinitionRegistry,
    get_default_definition_registry,
)
from typing import cast
from rekuest_next.api.schema import (
    AssignWidgetInput,
    DefinitionInput,
    DependencyInput,
    PortGroupInput,
    EffectInput,
    ImplementationInput,
    ValidatorInput,
)
from typing import (
    Dict,
    List,
    Callable,
    Optional,
    Tuple,
    TypeVar,
    Union,
    overload,
)
import inflection
from rekuest_next.actors.actify import reactify


def register_func(
    function_or_actor: AnyFunction,
    structure_registry: StructureRegistry,
    definition_registry: DefinitionRegistry,
    interface: str | None = None,
    name: str | None = None,
    actifier: Actifier = reactify,
    dependencies: List[DependencyInput] | None = None,
    port_groups: Optional[List[PortGroupInput]] = None,
    validators: Optional[Dict[str, List[ValidatorInput]]] = None,
    collections: List[str] | None = None,
    is_test_for: Optional[List[str]] = None,
    logo: Optional[str] = None,
    widgets: AssignWidgetMap | None = None,
    effects: Dict[str, List[EffectInput]] | None = None,
    interfaces: List[str] | None = None,
    on_provide: OnProvide | None = None,
    on_unprovide: OnUnprovide | None = None,
    dynamic: bool = False,
    in_process: bool = False,
    sync: Optional[SyncGroup] = None,
    stateful: bool = False,
) -> Tuple[DefinitionInput, ActorBuilder]:
    """Register a function or actor with the definition registry

    Register a function or actor with the definition registry. This will
    create a definition for the function or actor and register it with the
    definition registry.

    If first parameter is a function, it will be wrapped in an actorBuilder
    through the actifier. If the first parameter is an actor, it will be
    used as the actorBuilder (needs to have the dunder __definition__) to be
    detected as such.

    Args:
        function_or_actor (Union[Actor, Callable]): _description_
        actifier (Actifier, optional): _description_. Defaults to None.
        interface (str, optional): _description_. Defaults to None.
        widgets (Dict[str, WidgetInput], optional): _description_. Defaults to {}.
        interfaces (List[str], optional): _description_. Defaults to [].
        on_provide (_type_, optional): _description_. Defaults to None.
        on_unprovide (_type_, optional): _description_. Defaults to None.
        structure_registry (StructureRegistry, optional): _description_. Defaults to None.
    """

    interface = interface or inflection.underscore(
        function_or_actor.__name__
    )  # convert this to camelcase

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
            dependencies=tuple(dependencies or []),
            logo=logo,
            dynamic=dynamic,
        ),
        actor_builder,
    )

    return definition, actor_builder


T = TypeVar("T", bound=AnyFunction)


@overload
def register(
    func: T,
) -> T:
    """Register a function or actor to the default definition registry."""
    ...


@overload
def register(
    *,
    actifier: Actifier = reactify,
    interface: str | None = None,
    stateful: bool = False,
    widgets: Dict[str, AssignWidgetInput] | None = None,
    dependencies: List[DependencyInput] | None = None,
    interfaces: List[str] = [],
    collections: List[str] | None = None,
    port_groups: Optional[List[PortGroupInput]] = None,
    effects: Dict[str, List[EffectInput]] | None = None,
    is_test_for: Optional[List[str]] = None,
    logo: Optional[str] = None,
    on_provide: OnProvide | None = None,
    on_unprovide: OnUnprovide | None = None,
    validators: Optional[Dict[str, List[ValidatorInput]]] = None,
    structure_registry: StructureRegistry | None = None,
    definition_registry: DefinitionRegistry | None = None,
    in_process: bool = False,
    dynamic: bool = False,
    sync: Optional[SyncGroup] = None,
) -> Callable[[T], T]:
    """Register a function or actor to the default definition registry.

    You can use this decorator to register a function or actor to the default
    definition registry. There is also a function version of this decorator,
    which is more convenient to use.

    Example:
        >>> @register
        >>> def hello_world(string: str):

        >>> @register(interface="hello_world")
        >>> def hello_world(string: str):



    """

    ...


def register(
    *func: T,
    actifier: Actifier = reactify,
    interface: str | None = None,
    stateful: bool = False,
    widgets: Dict[str, AssignWidgetInput] | None = None,
    dependencies: List[DependencyInput] | None = None,
    interfaces: List[str] | None = None,
    collections: List[str] | None = None,
    port_groups: Optional[List[PortGroupInput]] = None,
    effects: Dict[str, List[EffectInput]] | None = None,
    is_test_for: Optional[List[str]] = None,
    logo: Optional[str] = None,
    on_provide: OnProvide | None = None,
    on_unprovide: OnUnprovide | None = None,
    validators: Optional[Dict[str, List[ValidatorInput]]] = None,
    structure_registry: StructureRegistry | None = None,
    definition_registry: DefinitionRegistry | None = None,
    in_process: bool = False,
    dynamic: bool = False,
    sync: Optional[SyncGroup] = None,
) -> Union[T, Callable[[T], T]]:
    """Register a function or actor to the default definition registry.

    You can use this decorator to register a function or actor to the default
    definition registry. There is also a function version of this decorator,
    which is more convenient to use.

    Example:
        >>> @register
        >>> def hello_world(string: str):

        >>> @register(interface="hello_world")
        >>> def hello_world(string: str):

    Args:
        function_or_actor (Union[Callable, Actor]): The function or Actor
        builder (ActorBuilder, optional): An actor builder (see ActorBuilder). Defaults to None.
        package (str, optional): The package you want to register this function in. Defaults to standard app package    .
        interface (str, optional): The name of the function. Defaults to the functions name.
        widgets (Dict[str, WidgetInput], optional): A dictionary of parameter key and a widget. Defaults to the default widgets as registered in the structure registry .
        interfaces (List[str], optional): Interfaces that this action adheres to. Defaults to [].
        on_provide (Callable[[Provision], Awaitable[dict]], optional): Function that shall be called on provide (in the async eventloop). Defaults to None.
        on_unprovide (Callable[[], Awaitable[dict]], optional): Function that shall be called on unprovide (in the async eventloop). Defaults to None.
        structure_registry (StructureRegistry, optional): The structure registry to use for this Actor (used to shrink and expand inputs). Defaults to None.
    """
    definition_registry = definition_registry or get_default_definition_registry()
    structure_registry = structure_registry or get_default_structure_registry()

    if len(func) > 1:
        raise ValueError("You can only register one function or actor at a time.")
    if len(func) == 1:
        function_or_actor = func[0]

        definition, _ = register_func(
            function_or_actor,
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

        return function_or_actor

    else:

        def real_decorator(function_or_actor: AnyFunction) -> AnyFunction:
            definition, _ = register_func(
                function_or_actor,
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

            return function_or_actor

        return cast(Callable[[T], T], real_decorator)  # type: ignore
