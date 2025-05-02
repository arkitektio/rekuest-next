"""Utility functions for Rekuest Next structures."""

from typing import Type
from .types import Predicator


def build_instance_predicate(cls: Type) -> Predicator:
    """Build a predicate function that checks if an object is an instance of the given class."""
    return lambda x: isinstance(x, cls)
