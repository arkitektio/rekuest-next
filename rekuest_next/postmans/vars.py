"""Postman context variable."""

import contextvars
from typing import Optional
from .types import Postman

current_postman: contextvars.ContextVar[Optional["Postman"]] = contextvars.ContextVar(
    "current_postman"
)


def get_current_postman() -> Postman | None:
    """Get the current postman.

    Returns:
        Postman: The current postman.
    """
    postman = current_postman.get(None)
    if postman is None:
        raise RuntimeError("No postman found in context")
    return postman
