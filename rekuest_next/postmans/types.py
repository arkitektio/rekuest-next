"""Postman types"""

from types import TracebackType
from typing import Any, AsyncGenerator, Dict, Optional, Protocol, runtime_checkable
from rekuest_next.api.schema import (
    AssignInput,
    TaskEventKind,
)


@runtime_checkable
class TaskEventLike(Protocol):
    """The parts of a task event that the call machinery actually reads.

    ``rekuest_next.remote._astream_raw`` only ever looks at ``.kind`` (compared against
    :class:`TaskEventKind`), ``.returns`` and ``.message``. Typing :meth:`Postman.aassign`
    against this instead of the concrete GraphQL ``TaskEventChange`` is what lets the
    agent-as-caller postman — which yields a lightweight
    :class:`~rekuest_next.agents.caller.CallerTaskEvent` adapter — genuinely satisfy
    :class:`Postman`.
    """

    @property
    def kind(self) -> TaskEventKind:
        """Which kind of event this is."""
        ...

    @property
    def returns(self) -> Optional[Dict[str, Any]]:
        """The yielded values, on a YIELD event."""
        ...

    @property
    def message(self) -> Optional[str]:
        """The error message, on a FAILED or CRITICAL event."""
        ...


@runtime_checkable
class Postman(Protocol):
    """Postman

    Postmans allow to wrap the async logic of the rekuest-server and

    """

    @property
    def connected(self) -> bool:
        """Whether the postman can currently originate work.

        Declared as a property, not an attribute: a mutable protocol attribute is
        invariant, so an implementation exposing this as a read-only property would not
        satisfy it.
        """
        ...

    def aassign(
        self,
        assign: AssignInput,
        escalate_to_interrupt: bool = False,
        cancel_timeout: Optional[float] = None,
    ) -> AsyncGenerator[TaskEventLike, None]:
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
