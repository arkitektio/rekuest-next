"""Postman types"""

from types import TracebackType
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    Optional,
    Protocol,
    Sequence,
    runtime_checkable,
)

from rath.scalars import ID

from rekuest_next.api.schema import (
    HookInput,
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
        *,
        args: Dict[str, Any],
        capture: bool = False,
        reference: Optional[str] = None,
        hooks: Optional[Sequence[HookInput]] = None,
        action: Optional[ID] = None,
        implementation: Optional[ID] = None,
        parent: Optional[ID] = None,
        dependency: Optional[str] = None,
        method: Optional[str] = None,
        escalate_to_interrupt: bool = False,
        cancel_timeout: Optional[float] = None,
    ) -> AsyncGenerator[TaskEventLike, None]:
        """Originate a task and stream its events.

        The call is described by its parameters rather than by a pre-built payload:
        the two transports that can originate work no longer share one. A GraphQL
        assign creates a *root* task (the backend dropped ``parent``/``dependency``/
        ``method`` from ``AssignInput``), while the agent socket carries the full tree
        (``messages.AssignRequest``) — so each postman builds its own wire model from
        these arguments, and neither has to know about the other's.

        Implementations may accept additional keyword arguments for whatever else
        their transport can express — ``action_hash``, ``agent``, ``interface``,
        ``resolution``, ``step`` on both, ``dependencies`` on GraphQL only. Those are
        deliberately not part of the protocol: nothing routes through it generically
        needs them, and requiring them would force every postman to model fields its
        transport does not have.

        Args:
            args: The task arguments (ports -> values).
            capture: Whether to run the task in debug capture mode.
            reference: Caller-supplied idempotency key, stable across resends of the
                same logical call. Minted by the postman when omitted.
            hooks: Lifecycle hooks to attach to the task.
            action: The action ID to assign to.
            implementation: The implementation ID to assign to directly.
            parent: The parent task ID, for a call made from inside a running task.
                Only the agent socket can express this.
            dependency: The dependency key to resolve, when running inside a resolved
                task. Only the agent socket can express this.
            method: The dependency method to assign. Only the agent socket can
                express this.
            escalate_to_interrupt: When the assign stream is cancelled, escalate to a
                forceful interrupt if the graceful cancel is not confirmed within the
                cancel timeout.
            cancel_timeout: Per-call override (seconds) for how long to await the
                cancel/interrupt confirmation. Falls back to the postman's default
                when ``None``.

        Raises:
            RootOnlyAssignError: By a root-only transport, if ``parent``,
                ``dependency`` or ``method`` is set.
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
