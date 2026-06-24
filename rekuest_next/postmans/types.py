"""Postman types"""

from types import TracebackType
from typing import AsyncGenerator, Optional, Protocol, runtime_checkable
from rekuest_next.api.schema import (
    AssignInput,
    TaskEventChange,
)


@runtime_checkable
class Postman(Protocol):
    """Postman

    Postmans allow to wrap the async logic of the rekuest-server and

    """

    connected: bool

    def aassign(
        self,
        assign: AssignInput,
        escalate_to_interrupt: bool = False,
        cancel_timeout: Optional[float] = None,
    ) -> AsyncGenerator[TaskEventChange, None]:
        """Assign.

        Args:
            assign: The assignation to send.
            escalate_to_interrupt: When the assign stream is cancelled, escalate to a
                forceful interrupt if the graceful cancel is not confirmed within the
                cancel timeout.
            cancel_timeout: Per-call override (seconds) for how long to await the
                cancel/interrupt confirmation. Falls back to the postman's default
                when ``None``.
        """
        ...

    async def __aenter__(self) -> "Postman":
        """Enter"""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit"""
        pass
