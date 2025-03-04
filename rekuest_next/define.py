from rekuest_next.agents.context import prepare_context_variables
from rekuest_next.definition.validate import hash_definition
from rekuest_next.state.state import prepare_state_variables
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
from rekuest_next.api.schema import (
    AssignWidgetInput,
    DependencyInput,
    PortGroupInput,
    EffectInput,
    ValidatorInput,
)
from typing import (
    Dict,
    List,
    Callable,
    Optional,
    TypeVar,
    overload,
)
import inflection
from rekuest_next.definition.define import prepare_definition
from functools import wraps


T = TypeVar("T")


@overload
def define(
    function_or_actor: T,
) -> T: ...


@overload
def define(
    interface: str = None,
    stateful: bool = False,
    widgets: Dict[str, AssignWidgetInput] = None,
    dependencies: List[DependencyInput] = None,
    interfaces: List[str] = [],
    collections: List[str] = None,
    port_groups: Optional[List[PortGroupInput]] = None,
    effects: Dict[str, List[EffectInput]] = None,
    is_test_for: Optional[List[str]] = None,
    logo: Optional[str] = None,
    on_provide=None,
    on_unprovide=None,
    validators: Optional[Dict[str, List[ValidatorInput]]] = None,
    structure_registry: StructureRegistry = None,
    definition_registry: DefinitionRegistry = None,
    in_process: bool = False,
    dynamic: bool = False,
    **actifier_params,
) -> Callable[[T], T]: ...


def define_func(
    function_or_actor,
    structure_registry: StructureRegistry,
    definition_registry: DefinitionRegistry,
    interface: str = None,
    stateful: bool = False,
    port_groups: Optional[List[PortGroupInput]] = None,
    groups: Optional[Dict[str, List[str]]] = None,
    validators: Optional[Dict[str, List[ValidatorInput]]] = None,
    collections: List[str] = None,
    is_test_for: Optional[List[str]] = None,
    widgets: Dict[str, AssignWidgetInput] = None,
    effects: Dict[str, List[EffectInput]] = None,
    interfaces: List[str] = [],
    **definition_params,
):
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

    state_variables, state_returns = prepare_state_variables(function_or_actor)
    context_variables, context_returns = prepare_context_variables(function_or_actor)

    if state_variables:
        stateful = True

    definition = prepare_definition(
        function_or_actor,
        structure_registry,
        widgets=widgets,
        interfaces=interfaces,
        port_groups=port_groups,
        collections=collections,
        stateful=stateful,
        validators=validators,
        effects=effects,
        is_test_for=is_test_for,
        **definition_params,
    )

    return definition


def define(
    *func,
    interface: str = None,
    stateful: bool = False,
    widgets: Dict[str, AssignWidgetInput] = None,
    dependencies: List[DependencyInput] = None,
    interfaces: List[str] = [],
    collections: List[str] = None,
    port_groups: Optional[List[PortGroupInput]] = None,
    effects: Dict[str, List[EffectInput]] = None,
    is_test_for: Optional[List[str]] = None,
    logo: Optional[str] = None,
    on_provide=None,
    on_unprovide=None,
    validators: Optional[Dict[str, List[ValidatorInput]]] = None,
    structure_registry: StructureRegistry = None,
    definition_registry: DefinitionRegistry = None,
    in_process: bool = False,
    dynamic: bool = False,
    **actifier_params,
):
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
        interfaces (List[str], optional): Interfaces that this node adheres to. Defaults to [].
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

        @wraps(function_or_actor)
        def wrapped_function(*args, **kwargs):
            return function_or_actor(*args, **kwargs)

        definition = define_func(
            function_or_actor,
            structure_registry=structure_registry,
            definition_registry=definition_registry,
            dependencies=dependencies,
            validators=validators,
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
            **actifier_params,
        )

        wrapped_function.__definition__ = definition
        wrapped_function.__definition_hash__ = hash_definition(definition)

        return wrapped_function

    else:

        def real_decorator(function_or_actor):
            # Simple bypass for now
            @wraps(function_or_actor)
            def wrapped_function(*args, **kwargs):
                return function_or_actor(*args, **kwargs)

            definition = define_func(
                function_or_actor,
                structure_registry=structure_registry,
                definition_registry=definition_registry,
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
                **actifier_params,
            )

            wrapped_function.__definition__ = definition
            wrapped_function.__definition_hash__ = hash_definition(definition)

            return wrapped_function

        return real_decorator


T = TypeVar("T")
