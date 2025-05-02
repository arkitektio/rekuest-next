"""Postman context variable."""

import contextvars
from .types import Postman

current_postman = contextvars.ContextVar("current_postman", default=None)


def get_current_postman() -> Postman:
    """Get the current postman.

    Returns:
        Postman: The current postman.
    """
    return current_postman.get()
