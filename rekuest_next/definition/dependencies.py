"""Dependencies module for Rekuest Next."""

from rekuest_next.actors.types import AnyFunction
from rekuest_next.api.schema import DependencyInput
from typing import Union


def declare(function_or_hash: Union[str, AnyFunction], optional: bool = False) -> DependencyInput:
    """Declare a function that needs to be
    called outside of your application.

    Args:
        function_or_hash (str or callable): The function or hash that needs to be declared.
        optional (bool, optional): Whether the dependency is optional. Defaults to False.

    Returns:
        DependencyInput: The dependency input object.

    """

    if callable(function_or_hash):
        definition_hash = getattr(function_or_hash, "__definition_hash__", None)
        if definition_hash is None:
            raise ValueError("Function must be registered before it can be declared")

        return DependencyInput(hash=definition_hash, optional=optional)

    else:
        assert isinstance(function_or_hash, str), "Only hash or function can be declared"
        return DependencyInput(hash=function_or_hash, optional=optional)
