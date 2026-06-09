"""Actifier

This module contains the actify function, which is used to convert a function
into an actor.
"""

import inspect
from functools import partial
from typing import Any, Optional, Tuple

from rekuest_next.actors.functional import (
    FunctionalFuncActor,
    FunctionalGenActor,
    FunctionalThreadedFuncActor,
    FunctionalThreadedGenActor,
)
from rekuest_next.actors.types import (
    ActorBuilder,
    AnyFunction,
    ImplementationDetails,
    RegisterConfig,
)
from rekuest_next.agents.context import (
    prepare_context_variables,
)
from rekuest_next.api.schema import (
    DefinitionInput,
)
from rekuest_next.definition.define import (
    prepare_definition,
)
from rekuest_next.state.utils import (
    prepare_state_variables,
)
from rekuest_next.agents.dependency import prepare_dependency_variables
from rekuest_next.structures.registry import StructureRegistry


def reactify(
    function: AnyFunction,
    structure_registry: StructureRegistry,
    config: Optional[RegisterConfig] = None,
) -> Tuple[DefinitionInput, ImplementationDetails, ActorBuilder]:
    """Reactify a function

    This function takes a callable (of type async or sync function or generator) and
    returns a builder function that creates an actor that makes the function callable
    from the rekuest server.

    All registration options are read from the bundled ``config``
    (:class:`~rekuest_next.actors.types.RegisterConfig`); ``config`` defaults to an
    empty config so ``reactify(func, registry)`` keeps working.
    """
    config = config or RegisterConfig()

    state_variables, state_returns = prepare_state_variables(function)
    context_variables, context_returns = prepare_context_variables(function)
    dependency_variables = prepare_dependency_variables(function)

    locks = config.locks
    if not locks and config.auto_locks:
        locks = []
        for lock in context_variables.required_context_locks.values():
            locks.extend(lock)
        for lock in state_variables.required_state_locks.values():
            locks.extend(lock)
        locks = list(set(locks))

    manipulates = config.manipulates
    if not manipulates:
        manipulates = []
        for state_name in state_variables.write_state_variables.values():
            manipulates.append(state_name)
        manipulates = list(set(manipulates))

    stateful = config.stateful
    if state_variables.count:
        stateful = True

    implementation_details = ImplementationDetails(
        state_variables=state_variables,
        state_returns=state_returns,
        context_variables=context_variables,
        context_returns=context_returns,
        dependency_variables=dependency_variables,
        locks=locks,
        tracks=config.tracks,
        manipulates=manipulates,
    )

    definition = prepare_definition(
        function,
        structure_registry,
        widgets=config.widgets,
        interfaces=config.interfaces,
        port_groups=config.port_groups,
        collections=config.collections,
        stateful=stateful,
        validators=config.validators,
        effects=config.effects,
        is_test_for=config.is_test_for,
        name=config.name,
        description=config.description,
        return_widgets=config.return_widgets,
        logo=config.logo,
        key=config.key,
        version=config.version,
    )

    is_coroutine = inspect.iscoroutinefunction(function)
    is_asyncgen = inspect.isasyncgenfunction(function)
    is_method = inspect.ismethod(function)

    is_generatorfunction = inspect.isgeneratorfunction(function)
    is_function = inspect.isfunction(function)

    actor_attributes: dict[str, Any] = {
        "assign": function,
        "expand_inputs": not config.bypass_expand,
        "shrink_outputs": not config.bypass_shrink,
        "structure_registry": structure_registry,
        "definition": definition,
        "state_variables": state_variables,
        "state_returns": state_returns,
        "context_variables": context_variables,
        "context_returns": context_returns,
        "dependency_variables": dependency_variables,
        "locks": locks,
    }

    if is_coroutine:
        return (
            definition,
            implementation_details,
            partial(FunctionalFuncActor, **actor_attributes),
        )
    elif is_asyncgen:
        return (
            definition,
            implementation_details,
            partial(FunctionalGenActor, **actor_attributes),
        )
    elif is_generatorfunction and not config.in_process:
        return (
            definition,
            implementation_details,
            partial(FunctionalThreadedGenActor, **actor_attributes),
        )
    elif (is_function or is_method) and not config.in_process:
        return (
            definition,
            implementation_details,
            partial(FunctionalThreadedFuncActor, **actor_attributes),
        )
    else:
        raise NotImplementedError("No way of converting this to a function")
