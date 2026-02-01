"""Context management for Rekuest Next."""

from typing import Tuple, Type, TypeVar
from typing import Dict, Any
import inspect

import inflection

from rekuest_next.definition.define import get_non_null_variants, is_tuple
from rekuest_next.protocols import AnyContext, AnyFunction


T = TypeVar("T")


def is_context(cls: T) -> bool:
    """Checks if the class is a context."""
    print(f"Checking if {cls} is a context")
    x = getattr(cls, "__rekuest_context__", False)
    print(f"Result: {x is not False}")
    return x is not False


def get_context_name(cls: T) -> str:
    """Returns the context name of the class."""

    x = getattr(cls, "__rekuest_context__", None)
    if x is None:
        raise ValueError(f"Class {cls} is not a context")
    return x


def context(cls: T) -> T:
    """Mark a class as a model. This is used to
    identify the model in the rekuest_next system."""

    setattr(cls, "__rekuest_context__", inflection.underscore(cls.__name__))

    return cls


def prepare_context_variables(
    function: AnyFunction,
) -> Tuple[Dict[str, Any], Dict[int, Any]]:
    """Prepares the context variables for a function.

    Args:
        function (Callable): The function to prepare the context variables for.

    Returns:
        Dict[str, Any]: A dictionary of context variables.
    """
    sig = inspect.signature(function)
    parameters = sig.parameters

    state_variables: Dict[str, str] = {}
    state_returns: Dict[int, str] = {}

    for key, value in parameters.items():
        cls = value.annotation
        if is_context(cls):
            state_variables[key] = cls.__rekuest_context__

    returns = sig.return_annotation

    if hasattr(returns, "_name"):
        if is_tuple(returns):
            print("Preparing context variables for tuple return type")
            for index, cls in enumerate(get_non_null_variants(returns)):
                print("Checking return value:", cls, "at index:", index)
                if is_context(cls):
                    state_returns[index] = cls.__rekuest_context__
        else:
            if is_context(returns):
                state_returns[0] = returns.__rekuest_context__

    return state_variables, state_returns
