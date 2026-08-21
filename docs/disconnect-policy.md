# Disconnect policy

An agent's connection to the platform is not just how results get reported — for
some actions it is part of the safety argument for starting them at all.

"Move the stage until I say stop" is only safe while *"I say stop"* is reachable.
If the control channel drops, the caller's cancel cannot land, and the motor keeps
going. For that class of action, losing the link is itself a stop condition.

A six-hour acquisition wants the exact opposite. Killing it because the network
blipped for three seconds is the bug, not the fix.

So rekuest splits the decision in two:

| Layer | Question | Where |
| --- | --- | --- |
| `ConnectionPolicy` | How hard should this **agent** fight to keep its link? | on the agent |
| `DisconnectPolicy` | What happens to **this action's** work while the link is down? | on `@register` |

## Per-action: `DisconnectPolicy`

The default is to keep running, so nothing that works today changes.

```python
from rekuest_next import register, CancelOnDisconnect


@register
def train_model(epochs: int) -> Model:
    """Rides out a disconnect. This is the default."""
    ...


@register(policy=CancelOnDisconnect())
def move_stage(direction: str) -> None:
    """Stops the moment control is lost."""
    ...


@register(policy=CancelOnDisconnect(grace=2.0))
def scan_tile(x: int, y: int) -> Image:
    """Tolerates a two-second blip, then stops."""
    ...
```

One `policy` argument rather than a pair of flags, so future dimensions can be
added without growing `register`'s already long signature.

When the link goes down, the agent starts a per-action countdown. If it comes back
inside the grace period, nothing happens. If it does not, the work is cancelled and
reported to the backend as terminal. That report is retained and replayed as soon as
the link returns, so a kill that happens while the socket is down is not lost with
it.

Actions that did not declare the policy are untouched. A drop can stop the stage
while the acquisition running beside it on the same agent keeps going.

## Sync actions must cooperate

`task.cancel()` raises at the next `await`. A sync (non-`async`) action runs in a
koil worker thread, and **a thread cannot be force-killed**. The honest contract is:
we raise into it at the next `check_cancelled()`, and a body that never polls will
not stop.

```python
from koil import check_cancelled


@register(policy=CancelOnDisconnect())
def move_stage(direction: str) -> None:
    while motor.moving():
        check_cancelled()   # required — without this the loop never stops
        motor.step()
```

Registering a sync action with `CancelOnDisconnect` emits a warning at import, so
the gap is visible rather than silently assumed away.

## Per-agent: `ConnectionPolicy`

How long to keep trying before giving up on the link entirely.

```python
from rekuest_next import ConnectionPolicy, Backoff, RekuestAgent

agent = RekuestAgent(
    connection_policy=ConnectionPolicy(
        max_retries=5,
        backoff=Backoff(initial=1.0, factor=2.0, max=60.0, jitter=0.1),
        reset_after=30.0,
    ),
    ...
)
```

`max_retries` bounds *consecutive* failures. What makes that bound mean anything is
`reset_after`: the budget is only refunded once a connection has stood up for that
long. Without it, a link that connects and immediately drops resets the counter
every cycle and retries forever.

`flap_limit` / `flap_window` are an optional sliding-window backstop for the one
case `reset_after` cannot see — a link that stays up for slightly *longer* than
`reset_after` on every cycle. Off by default.

When the budget runs out the agent tears down, which cancels all in-flight work
regardless of policy.

> **Migration.** `max_retries`, `time_between_retries` and `allow_reconnect` on
> `WebsocketAgentTransport` are deprecated. They still work and still take
> precedence over the agent's policy, but they warn.

## What this does not cover

This closes the window where the *network* is gone or the server is restarting. It
is **not** a safety-rated interlock:

- If the agent process itself wedges, is `SIGKILL`ed, or loses power, no in-process
  watchdog can fire.
- A sync action that never polls `check_cancelled()` will not stop.

Anything that must stop for real when its controller goes away needs a watchdog in
the hardware controller too. Treat this as reducing the window, not eliminating it.
