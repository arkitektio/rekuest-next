from typing import Any, Dict, Optional, runtime_checkable, Protocol

from rekuest_next.messages import Assign


@runtime_checkable
class RPCContract(Protocol):
    """An RPC contract is a protocol that defines how
    to call a function or generator in a blocking or non-blocking way.
    """

    async def __aenter__(self) -> "RPCContract": ...

    async def acall_raw(
        self,
        kwargs: Dict[str, Any],
        parent: Optional[Assign] = None,
        reference: str = None,
        assign_timeout: Optional[float] = None,
        timeout_is_recoverable: bool = False,
    ): ...

    async def aiterate_raw(
        self,
        kwargs: Dict[str, Any],
        parent: Optional[Assign] = None,
        reference: str = None,
        assign_timeout: Optional[float] = None,
        timeout_is_recoverable: bool = False,
    ): ...

    async def __aexit__(self, exc_type, exc_val, exc_tb): ...

    def __enter__(self) -> "RPCContract":
        return super().__enter__()
