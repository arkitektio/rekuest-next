"""Context management for Rekuest Next."""

from typing import Tuple, Type, TypeVar
from typing import Dict, Any
import inspect

import inflection

from rekuest_next.protocols import AnyContext, AnyFunction


T = TypeVar("T", bound=Type[AnyContext])


def is_context(cls: Type[T]) -> bool:
    """Checks if the class is a context."""
    return getattr(cls, "__rekuest_context__", False)


def get_context_name(cls: Type[T]) -> str:
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
        if returns._name == "Tuple":
            for index, cls in enumerate(returns.__args__):
                if is_context(cls):
                    state_returns[index] = cls.__rekuest_context__
        else:
            if is_context(returns):
                state_returns[0] = returns.__rekuest_context__

    return state_variables, state_returns
