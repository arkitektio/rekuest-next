"""Actifier

This module contains the actify function, which is used to convert a function
into an actor.
"""

import inspect
from functools import partial
from typing import Any, Dict, List, Optional, Tuple

from rekuest_next.actors.functional import (
    FunctionalFuncActor,
    FunctionalGenActor,
    FunctionalThreadedFuncActor,
    FunctionalThreadedGenActor,
)
from rekuest_next.actors.sync import SyncGroup
from rekuest_next.actors.types import ActorBuilder, AnyFunction, OnProvide, OnUnprovide
from rekuest_next.agents.context import prepare_context_variables
from rekuest_next.api.schema import (
    DefinitionInput,
    PortGroupInput,
    ValidatorInput,
)
from rekuest_next.definition.define import (
    AssignWidgetMap,
    EffectsMap,
    ReturnWidgetMap,
    prepare_definition,
)
from rekuest_next.state.utils import prepare_state_variables
from rekuest_next.structures.registry import StructureRegistry


def reactify(
    function: AnyFunction,
    structure_registry: StructureRegistry,
    bypass_shrink: bool = False,
    bypass_expand: bool = False,
    on_provide: Optional[OnProvide] = None,
    on_unprovide: Optional[OnUnprovide] = None,
    description: str | None = None,
    stateful: bool = False,
    validators: Optional[Dict[str, List[ValidatorInput]]] = None,
    collections: List[str] | None = None,
    effects: EffectsMap | None = None,
    port_groups: Optional[List[PortGroupInput]] = None,
    is_test_for: Optional[List[str]] = None,
    widgets: AssignWidgetMap | None = None,
    return_widgets: ReturnWidgetMap | None = None,
    interfaces: List[str] | None = None,
    in_process: bool = False,
    logo: str | None = None,
    name: str | None = None,
    sync: Optional[SyncGroup] = None,
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
        name=name,
        description=description,
        return_widgets=return_widgets,
        logo=logo,
    )

    is_coroutine = inspect.iscoroutinefunction(function)
    is_asyncgen = inspect.isasyncgenfunction(function)
    is_method = inspect.ismethod(function)

    is_generatorfunction = inspect.isgeneratorfunction(function)
    is_function = inspect.isfunction(function)

    actor_attributes: dict[str, Any] = {
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
        return definition, partial(FunctionalFuncActor, **actor_attributes)
    elif is_asyncgen:
        return definition, partial(FunctionalGenActor, **actor_attributes)
    elif is_generatorfunction and not in_process:
        return definition, partial(FunctionalThreadedGenActor, **actor_attributes)
    elif (is_function or is_method) and not in_process:
        return definition, partial(FunctionalThreadedFuncActor, **actor_attributes)
    else:
        raise NotImplementedError("No way of converting this to a function")
