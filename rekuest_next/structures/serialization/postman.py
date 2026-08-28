"""Serialization for the postman (client → server → client) path.

The actual implementations live in :mod:`.shrink` and :mod:`.expand`; they are
shared with the actor-side dependency-call path.
"""

from .expand import aexpand_return, aexpand_returns
from .shrink import ashrink_arg, ashrink_args

__all__ = ["ashrink_arg", "ashrink_args", "aexpand_return", "aexpand_returns"]
