"""Actifier

This module contains the actify function, which is used to convert a function
into an actor.
"""

import inspect
from typing import Awaitable, Callable, Dict, List, Optional, Tuple

from rekuest_next.agents.context import prepare_context_variables
from rekuest_next.state.decorator import prepare_state_variables
from rekuest_next.api.schema import ValidatorInput
from rekuest_next.actors.functional import (
    SerializingActor,
    FunctionalFuncActor,
    FunctionalGenActor,
    FunctionalThreadedFuncActor,
    FunctionalThreadedGenActor,
)
from rekuest_next.actors.types import Actor, ActorBuilder
from rekuest_next.api.schema import (
    DefinitionInput,
    EffectInput,
    PortGroupInput,
    AssignWidgetInput,
)
from rekuest_next.definition.define import prepare_definition
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.actors.sync import SyncGroup


def higher_order_builder(
    builder: ActorBuilder, **params: Dict[str, object]
) -> ActorBuilder:
    """Higher order builder for actors#

    This is a higher order builder for actors. It takes a Actor class and
    returns a builder function that inserts the parameters into the class
    constructor. Akin to a partial function.
    """

    def inside_builder(**kwargs: Dict[str, object]) -> Actor:
        return builder(
            **kwargs,
            **params,
        )

    return inside_builder


def reactify(
    function: Callable,
    structure_registry: StructureRegistry,
    bypass_shrink: bool = False,
    bypass_expand: bool = False,
    on_provide: Optional[Callable[[SerializingActor], Awaitable[None]]] = None,
    on_unprovide: Optional[Callable[[SerializingActor], Awaitable[None]]] = None,
    stateful: bool = False,
    validators: Optional[Dict[str, List[ValidatorInput]]] = None,
    collections: List[str] = None,
    effects: Dict[str, EffectInput] = None,
    port_groups: Optional[List[PortGroupInput]] = None,
    is_test_for: Optional[List[str]] = None,
    widgets: Dict[str, AssignWidgetInput] = None,
    interfaces: List[str] = [],
    in_process: bool = False,
    sync: Optional[SyncGroup] = None,
    **params: Dict[str, object],
) -> Tuple[DefinitionInput, ActorBuilder]:
    """Reactify a function

    This function takes a callable (of type async or sync function or generator) and
    returns a builder function that creates an actor that makes the function callable
    from the rekuest server.
    """

    state_variables, state_returns = prepare_state_variables(function)
    context_variables, context_returns = prepare_context_variables(function)

    if state_variables:
        stateful = True

    definition = prepare_definition(
        function,
        structure_registry,
        widgets=widgets,
        interfaces=interfaces,
        port_groups=port_groups,
        collections=collections,
        stateful=stateful,
        validators=validators,
        effects=effects,
        is_test_for=is_test_for,
        **params,
    )

    is_coroutine = inspect.iscoroutinefunction(function)
    is_asyncgen = inspect.isasyncgenfunction(function)
    is_method = inspect.ismethod(function)

    is_generatorfunction = inspect.isgeneratorfunction(function)
    is_function = inspect.isfunction(function)

    actor_attributes = {
        "assign": function,
        "expand_inputs": not bypass_expand,
        "shrink_outputs": not bypass_shrink,
        "on_provide": on_provide,
        "on_unprovide": on_unprovide,
        "structure_registry": structure_registry,
        "definition": definition,
        "state_variables": state_variables,
        "state_returns": state_returns,
        "context_variables": context_variables,
        "context_returns": context_returns,
        "sync": sync,
    }

    if is_coroutine:
        return definition, higher_order_builder(FunctionalFuncActor, **actor_attributes)
    elif is_asyncgen:
        return definition, higher_order_builder(FunctionalGenActor, **actor_attributes)
    elif is_generatorfunction and not in_process:
        return definition, higher_order_builder(
            FunctionalThreadedGenActor, **actor_attributes
        )
    elif (is_function or is_method) and not in_process:
        return definition, higher_order_builder(
            FunctionalThreadedFuncActor, **actor_attributes
        )
    else:
        raise NotImplementedError("No way of converting this to a function")
