"""Decorator to register a class as a state."""

from rekuest_next.actors.types import (
    AnyFunction,
    PreparedAppContextReturns,
    PreparedAppContextVariables,
    PreparedStateReturns,
    PreparedStateVariables,
)
from rekuest_next.definition.define import (
    get_non_null_variants,
    is_none_type,
    is_nullable,
    is_tuple,
)
from rekuest_next.state.predicate import (
    get_state_locks,
    get_state_name,
    is_app_context,
    is_read_only_state,
    is_state,
)
from typing import Tuple
from typing import Dict, Any
import inspect


def get_return_length(signature: inspect.Signature) -> int:
    """Get the length of the return annotation of a function signature.

    Args:
        signature (inspect.Signature): The function signature.
    Returns:
        int: The length of the return annotation.
    """
    returns = signature.return_annotation

    if is_tuple(returns):
        return len(get_non_null_variants(returns))
    if is_none_type(returns):
        return 0
    else:
        return 1
    return 0


def prepare_state_variables(
    function: AnyFunction,
) -> Tuple[PreparedStateVariables, PreparedStateReturns]:
    """Prepare the state variables for the function.

    Args:
        function (Callable): The function to prepare the state variables for.

    Returns:
        Tuple[PreparedStateVariables, PreparedStateReturns]: The state variables and state returns for the function.

    """
    sig = inspect.signature(function)
    parameters = sig.parameters

    write_state_variables: Dict[str, str] = {}
    read_only_variables: Dict[str, str] = {}
    required_state_locks: Dict[str, list[str]] = {}
    state_returns: Dict[int, str] = {}

    for key, value in parameters.items():
        print(key, value.annotation)
        if is_state(value.annotation):
            print(f"Found state variable: {key} of type {value.annotation}")
            write_state_variables[key] = get_state_name(value.annotation)
            required_state_locks[key] = get_state_locks(value.annotation)
        elif is_read_only_state(value.annotation):
            read_only_variables[key] = get_state_name(value.annotation)

    returns = sig.return_annotation
    print(f"Return annotation: {returns}")

    if is_tuple(returns):
        for index, cls in enumerate(get_non_null_variants(returns)):
            if is_state(cls):
                state_returns[index] = get_state_name(cls)
    else:
        print(f"Return annotation: {returns}")
        if is_state(returns):
            state_returns[0] = get_state_name(returns)

    return PreparedStateVariables(
        write_state_variables=write_state_variables,
        read_only_variables=read_only_variables,
        required_state_locks=required_state_locks,
    ), PreparedStateReturns(state_returns=state_returns)


def prepare_appcontext(
    function: AnyFunction,
) -> Tuple[PreparedAppContextVariables, PreparedAppContextReturns]:
    """Prepare the state variables for the function.

    Args:
        function (Callable): The function to prepare the state variables for.

    Returns:
        Tuple[PreparedStateVariables, PreparedStateReturns]: The state variables and state returns for the function.

    """
    sig = inspect.signature(function)
    parameters = sig.parameters

    write_app_context_variables: Dict[str, str] = {}
    for key, value in parameters.items():
        if is_app_context(value.annotation):
            write_app_context_variables[key] = value.annotation.__rekuest_app_context__

    returns = sig.return_annotation

    app_context_returns: Dict[int, str] = {}
    print(f"Return annotation: {returns}")

    if is_tuple(returns):
        for index, cls in enumerate(get_non_null_variants(returns)):
            if is_app_context(cls):
                app_context_returns[index] = value.annotation.__rekuest_app_context__
    else:
        print(f"Return annotation: {returns}")
        if is_app_context(returns):
            app_context_returns[0] = value.annotation.__rekuest_app_context__

    return PreparedAppContextVariables(
        app_context_variables=write_app_context_variables,
    ), PreparedAppContextReturns(app_context_returns=app_context_returns)
