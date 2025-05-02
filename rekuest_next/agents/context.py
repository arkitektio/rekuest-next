"""Context management for Rekuest Next."""

from typing import Type, TypeVar, Callable
from typing import Dict, Any, overload
import inspect


T = TypeVar("T")


def is_context(cls: Type[T]) -> bool:
    """Checks if the class is a context."""
    return getattr(cls, "__rekuest_context__", False)


def get_context_name(cls: Type[T]) -> str:
    """Returns the context name of the class."""

    x = getattr(cls, "__rekuest_context__", None)
    if x is None:
        raise ValueError(f"Class {cls} is not a context")
    return x


@overload
def context(cls: Type[T]) -> Type[T]:
    """Decorator to mark a class as a context.

    Args:
        cls (Type[T]): The class to mark as a context.
        name (str): The name of the context. If not provided, the class name will be used.
    """
    ...


@overload
def context(name: str) -> Callable[[Type[T]], Type[T]]:
    """Decorator to mark a class as a context.

    Args:
        name (str): The name of the context. If not provided, the class name will be used.
    """
    ...


def context(*func, name: str = None) -> Callable[[Type[T]], Type[T]]:
    """Decorator to mark a class as a context.

    Args:
        cls (Type[T]): The class to mark as a context.
        name (str): The name of the context. If not provided, the class name will be used.
    """
    if len(func) == 1 and not isinstance(func[0], str):
        cls = func[0]
        setattr(cls, "__rekuest_context__", cls.__name__)

        return cls

    else:

        def wrapper(cls: Type[T]) -> Type[T]:
            setattr(cls, "__rekuest_context__", name)
            return cls

        return wrapper


def prepare_context_variables(function: Callable) -> Dict[str, Any]:
    """Prepares the context variables for a function.

    Args:
        function (Callable): The function to prepare the context variables for.

    Returns:
        Dict[str, Any]: A dictionary of context variables.
    """
    sig = inspect.signature(function)
    parameters = sig.parameters

    state_variables = {}
    state_returns = {}

    for key, value in parameters.items():
        cls = value.annotation
        if is_context(cls):
            state_variables[key] = cls.__rekuest_context__

    returns = sig.return_annotation

    if hasattr(returns, "_name"):
        if returns._name == "Tuple":
            for index, cls in enumerate(returns.__args__):
                if is_context(cls):
                    state_returns[index] = cls.__rekuest_state__
        else:
            if is_context(returns):
                state_returns[0] = returns.__rekuest_state__

    return state_variables, state_returns
