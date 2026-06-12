"""Context management for Rekuest Next."""

from typing import Callable, Dict, Optional, Tuple, Type, TypeVar, overload, get_type_hints
import inspect
from dataclasses import dataclass
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
    """Mark a class as agent context metadata.

    The decorator does not wrap the class behavior. Instead, it annotates the
    class with ``__rekuest_context__`` and ``__rekuest_context_locks__`` so
    startup hooks, background tasks, and action signatures can request the
    context by type. Lock names declared here are collected during signature
    inspection and used to serialize access where needed.

    Args:
        *function: Class to decorate when used as ``@context`` without
            parentheses.
        name: Explicit exported context name. Defaults to the snake_case class
            name.
        locks: Optional lock names required when this context is injected.

    Returns:
        The decorated class, or a decorator configured with the provided
        metadata.

    Raises:
        ValueError: If more than one class is passed at once.

    Examples:
        Register a shared context class::

            @context(name="camera_session", locks=["camera"])
            class CameraSession:
                device_id: str
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


@dataclass
class PreparedContextVariables:
    context_variables: Dict[str, str]
    required_context_locks: Dict[str, list[str]]

    @property
    def count(self) -> int:
        """Get the amount of state variables."""
        return len(self.context_variables)


@dataclass
class PreparedContextReturns:
    context_returns: Dict[int, str]

    @property
    def count(self) -> int:
        """Get the amount of context variables."""
        return len(self.context_returns)


def prepare_context_variables(
    function: AnyFunction,
) -> Tuple[PreparedContextVariables, PreparedContextReturns]:
    """Prepares the context variables for a function.

    Args:
        function (Callable): The function to prepare the context variables for.

    Returns:
        Dict[str, Any]: A dictionary of context variables.
    """
    sig = inspect.signature(function)
    parameters = sig.parameters

    try:
        hints = get_type_hints(function, include_extras=True)
    except Exception:
        hints = {}

    state_variables: Dict[str, str] = {}
    state_returns: Dict[int, str] = {}
    required_locks: Dict[str, list[str]] = {}

    for key, value in parameters.items():
        cls = hints.get(key, value.annotation)
        if is_context(cls):
            state_variables[key] = cls.__rekuest_context__
            required_locks[key] = get_context_locks(cls)

    returns = hints.get("return", sig.return_annotation)

    if is_tuple(returns):
        for index, cls in enumerate(get_non_null_variants(returns)):
            if is_context(cls):
                state_returns[index] = cls.__rekuest_context__
    else:
        if is_context(returns):
            state_returns[0] = returns.__rekuest_context__

    return (
        PreparedContextVariables(
            context_variables=state_variables, required_context_locks=required_locks
        ),
        PreparedContextReturns(context_returns=state_returns),
    )
