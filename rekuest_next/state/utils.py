"""Decorator to register a class as a state."""

from rekuest_next.actors.types import AnyFunction
from rekuest_next.state.predicate import get_state_name, is_state
from typing import Tuple
from typing import Dict, Any
import inspect


def prepare_state_variables(
    function: AnyFunction,
) -> Tuple[Dict[str, Any], Dict[int, Any]]:
    """Prepare the state variables for the function.

    Args:
        function (Callable): The function to prepare the state variables for.

    Returns:
        Dict[str, Any]: The state variables for the function.
    """
    sig = inspect.signature(function)
    parameters = sig.parameters

    state_variables: Dict[str, str] = {}
    state_returns: Dict[int, str] = {}

    for key, value in parameters.items():
        if is_state(value.annotation):
            state_variables[key] = get_state_name(value.annotation)

    returns = sig.return_annotation

    if hasattr(returns, "_name"):
        if returns._name == "Tuple":
            for index, cls in enumerate(returns.__args__):
                if is_state(cls):
                    state_returns[index] = get_state_name(cls)
        else:
            if is_state(returns):
                state_returns[0] = get_state_name(returns)

    return state_variables, state_returns
