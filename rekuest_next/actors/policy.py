"""What happens to an action's in-flight work when the control channel is lost.

For some actions the ability to cancel is part of the safety argument for starting
them at all. "Move the stage until I say stop" is only safe while "I say stop" is
reachable, so losing the link is itself a stop condition — for that class of action,
and only that class. A six-hour acquisition wants the opposite: dying on a
three-second blip is the bug.

Hence a per-action declaration, defaulting to :attr:`OnDisconnect.KEEP` so nothing
that works today changes. The agent-level half of the story — how hard to fight for
the link in the first place — lives in :mod:`rekuest_next.agents.policy`.

This policy is client-local. It is never sent to the backend, and it could not be:
the server cannot reach a disconnected agent, so the whole property has to be
enforced in-process.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["OnDisconnect", "DisconnectPolicy", "KEEP", "CancelOnDisconnect"]


class OnDisconnect(str, Enum):
    """What to do with in-flight work when the agent loses its control channel."""

    KEEP = "keep"
    """Let it run. The default, and what every action did before this existed."""

    CANCEL = "cancel"
    """Stop it once the link has been down for longer than the grace period."""


class DisconnectPolicy(BaseModel):
    """Per-action behaviour while the agent's control channel is down."""

    model_config = ConfigDict(frozen=True)

    on_disconnect: OnDisconnect = Field(
        default=OnDisconnect.KEEP,
        description="Whether to keep running or cancel when the link drops.",
    )
    grace: float = Field(
        default=0.0,
        description=(
            "Seconds of downtime tolerated before cancelling. 0 means the work stops "
            "as soon as the link does. Ignored when ``on_disconnect`` is KEEP."
        ),
    )

    @property
    def cancels_on_disconnect(self) -> bool:
        """Whether this policy stops work when the link goes down."""
        return self.on_disconnect is OnDisconnect.CANCEL


KEEP = DisconnectPolicy()
"""The default policy: in-flight work survives a disconnect."""


def CancelOnDisconnect(grace: float = 0.0) -> DisconnectPolicy:  # noqa: N802
    """Stop this action's work when the control channel is lost.

    Named like a constructor because that is how it reads at a registration site::

        @register(policy=CancelOnDisconnect(grace=2.0))
        def move_stage(direction: str) -> None: ...

    Args:
        grace: Seconds of downtime to tolerate first. Defaults to none.
    """
    return DisconnectPolicy(on_disconnect=OnDisconnect.CANCEL, grace=grace)
