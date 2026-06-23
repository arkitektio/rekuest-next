"""Context management for Rekuest Next."""

from rekuest_next.declare import DeclaredAgentProtocol

from typing import Dict, Any
import inspect

from rekuest_next.actors.types import PreparedDependencyVariables
from rekuest_next.definition.define import (
    get_non_null_variants,
    is_dependency_type,
    is_tuple,
)
from rekuest_next.protocols import AnyFunction


def prepare_dependency_variables(
    function: AnyFunction,
) -> PreparedDependencyVariables:
    """Prepares the context variables for a function.

    Detects the dependency variables from the function's signature and returns them as a dictionary.

    It also checks the return type of the function to ensure that dependency variables are not returned as tuples or single values, raising a NotImplementedError if they are.


    Args:
        function (Callable): The function to prepare the context variables for.

    Returns:
        Dict[str, Any]: A dictionary of context variables.
    """
    sig = inspect.signature(function)
    parameters = sig.parameters

    depedency_variables: Dict[str, str] = {}

    for key, value in parameters.items():
        cls = value.annotation
        if is_dependency_type(cls):
            depedency_variables[key] = cls

    returns = sig.return_annotation

    if hasattr(returns, "_name"):
        if is_tuple(returns):
            for _, cls in enumerate(get_non_null_variants(returns)):
                if is_dependency_type(cls):
                    raise NotImplementedError(
                        "Dependency variables cannot be returned as tuples."
                    )
        else:
            if is_dependency_type(returns):
                raise NotImplementedError(
                    "Dependency variables cannot be returned as single values."
                )
    return PreparedDependencyVariables(dependency_variables=depedency_variables)


def dependency_to_protocol(cls: Any) -> DeclaredAgentProtocol[Any]:
    """Convert a dependency class to a AgentProtocol"""
    dependency = getattr(cls, "__rekuest__dependency__")
    assert dependency is not None, (
        f"Class {cls} does not have a __rekuest__dependency__ attribute"
    )
    return dependency
