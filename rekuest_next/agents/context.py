"""Context management for Rekuest Next."""

from typing import Callable, List, Optional, Tuple, Type, TypeVar, overload
from typing import Dict, Any
import inspect

import inflection

from rekuest_next.definition.define import get_non_null_variants, is_tuple
from rekuest_next.protocols import AnyContext, AnyFunction


T = TypeVar("T", bound=AnyContext)


def is_context(cls: object) -> bool:
    """Checks if the class is a context."""
    x = getattr(cls, "__rekuest_context__", False)
    return x is not False


def get_context_name(cls: object) -> str:
    """Returns the context name of the class."""

    x = getattr(cls, "__rekuest_context__", None)
    if x is None:
        raise ValueError(f"Class {cls} is not a context")
    return x


def get_context_locks(cls: object) -> list[str]:
    """Returns the context locks of the class."""

    x = getattr(cls, "__rekuest_context_locks__", [])
    return x


@overload
def context(
    *function: Type[T],
) -> Type[T]:
    """Decorator to register a class as a context."""
    ...


@overload
def context(
    *,
    name: Optional[str] = None,
    locks: Optional[list[str]] = None,
) -> Callable[[T], T]:
    """Decorator to register a class as a context with optional locks.

    Args:
        name (Optional[str]): The name of the context. If None, the class name will be used.
        local_only (bool): If True, the context will only be available locally.
        locks (Optional[list[str]]): A list of locks for the context. If None, no locks will be used.
    """
    ...


def context(  # type: ignore[valid-type]
    *function: Type[T],
    name: Optional[str] = None,
    locks: Optional[list[str]] = None,
) -> Type[T] | Callable[[Type[T]], Type[T]]:
    """Decorator to register a class as a context.

    Context classes are used to store information that should be visible to the user
    of the system and might change between action calls. Examples of context include
    the position of a robot arm, the current settings of a device, or the status of
    a process.

    Context can be changed by any action if it declares it as an argument.
    During this passing the context is locked for the duration of the action call,
    preventing race conditions. When the action has finished, the new context is published.




    Args:
        name_or_function (Type[T]): The class to register
        local_only (bool): If True, the context will only be available locally.
        name (Optional[str]): The name of the context. If None, the class name will be used.
        locks (Optional[list[str]]): A list of locks for the context. If None, no locks will be used.

    Returns:
        Callable[[Type[T]], Type[T]]: The decorator function.


    """

    if len(function) == 1:
        cls = function[0]
        return context(name=cls.__name__)(cls)

    if len(function) == 0:

        def wrapper(cls: Type[T]) -> Type[T]:
            setattr(
                cls, "__rekuest_context__", inflection.underscore(name or cls.__name__)
            )
            setattr(cls, "__rekuest_context_locks__", locks or [])
            return cls

        return wrapper

    raise ValueError("You can only register one class at a time.")


def prepare_context_variables(
    function: AnyFunction,
) -> Tuple[Dict[str, Any], Dict[int, Any], Dict[str, list[str]]]:
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
    required_locks: Dict[str, list[str]] = {}

    for key, value in parameters.items():
        cls = value.annotation
        if is_context(cls):
            state_variables[key] = cls.__rekuest_context__
            required_locks[key] = get_context_locks(cls)

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
    return state_variables, state_returns, required_locks


def get_all_context_locks(cls: List[Type[AnyContext]]) -> list[str]:
    """Returns the context variable for a given context class.

    Args:
        cls (Type[AnyContext]): The context class to get the variable for.
    """
    locks: list[str] = []
    for c in cls:
        locks.extend(get_context_locks(c))
    return list(set(locks))
