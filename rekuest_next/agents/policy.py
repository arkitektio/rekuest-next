"""How hard an agent fights to keep its control channel.

The agent owns this policy; the transport merely executes it. That split matters
because the transport owns the *socket* but only the agent knows what is riding on
it — see :mod:`rekuest_next.actors.policy` for the other half, where each action
declares what should happen to *its* in-flight work while the link is down.

The two are designed together. Being patient about reconnecting is only safe once
dangerous actions can opt out of waiting.
"""

import random
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["Backoff", "ConnectionPolicy"]


class Backoff(BaseModel):
    """Exponential backoff between reconnect attempts.

    Delay for attempt *n* (0-based) is ``min(initial * factor**n, max)``, then
    perturbed by up to ``jitter`` of itself in either direction so that a fleet of
    agents reconnecting after a server restart does not arrive in lockstep.
    """

    model_config = ConfigDict(frozen=True)

    initial: float = Field(
        default=1.0, description="Delay before the first retry, in seconds."
    )
    factor: float = Field(
        default=2.0, description="Multiplier applied to the delay after each attempt."
    )
    max: float = Field(
        default=60.0, description="Ceiling for a single delay, in seconds."
    )
    jitter: float = Field(
        default=0.1,
        description=(
            "Fraction of the computed delay to randomise by, applied symmetrically. "
            "0 disables jitter (making delays deterministic, which tests rely on)."
        ),
    )

    def delay_for(self, attempt: int) -> float:
        """The delay to wait before retry number ``attempt`` (0-based)."""
        raw = min(self.initial * (self.factor**attempt), self.max)
        if not self.jitter:
            return raw
        return max(0.0, raw + raw * random.uniform(-self.jitter, self.jitter))


class ConnectionPolicy(BaseModel):
    """The agent's reconnect budget.

    ``max_retries`` bounds *consecutive* failures. What makes that bound meaningful
    is ``reset_after``: the budget is only returned once a connection has stood up
    for that long. Without it a link that connects and immediately drops resets the
    counter every cycle and retries forever — which is what the agent did before
    this policy existed.
    """

    model_config = ConfigDict(frozen=True)

    max_retries: int = Field(
        default=5,
        description="Consecutive failed connect attempts tolerated before giving up.",
    )
    backoff: Backoff = Field(
        default_factory=Backoff, description="Delay schedule between attempts."
    )
    reset_after: float = Field(
        default=30.0,
        description=(
            "Seconds a connection must stay up before the retry budget is reset. A "
            "shorter-lived connection does not count as recovery."
        ),
    )
    flap_limit: int | None = Field(
        default=None,
        description=(
            "Sliding-window backstop: give up after this many drops within "
            "``flap_window``, regardless of how long each connection lasted. ``None`` "
            "disables it, leaving ``reset_after`` as the only bound — which is enough "
            "unless the link is stable for slightly longer than ``reset_after`` on "
            "every cycle."
        ),
    )
    flap_window: float = Field(
        default=300.0, description="Width of the ``flap_limit`` window, in seconds."
    )
    on_exhausted: Literal["shutdown"] = Field(
        default="shutdown",
        description=(
            "What to do once the budget is spent. Only ``shutdown`` (tear the agent "
            "down, the pre-existing behaviour) is implemented; the field exists so "
            "that a ``keep_retrying`` mode for unattended field agents can be added "
            "without changing the signature."
        ),
    )
