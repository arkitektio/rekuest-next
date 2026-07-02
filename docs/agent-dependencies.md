# Agent dependencies

An app rarely works alone. A workflow app might need a *camera* agent to acquire
frames and a *viewer* agent to display them; a stitching app needs the *stage* it
drives to expose a known state. rekuest lets you declare those needs as a **agent
dependency protocol** — a plain class whose methods describe the **actions** you
call and whose annotated attributes describe the **states** you read.

The platform then resolves each dependency to a concrete, running agent that
satisfies it — either automatically (`auto_resolvable`) or by asking the user to
pick one when your implementation is set up.

```python
from rekuest_next import declare, declare_state


@declare_state
class CameraState:
    connected: bool
    exposure_ms: float


@declare(app="mymicroscope")
class CameraDeps:
    """A camera agent this app needs to drive."""

    state: CameraState  # a state demand

    async def acquire(self, exposure_ms: float) -> bytes:  # an action demand
        """Acquire a single frame."""
        ...
```

Two passes turn this class into a dependency:

- **public methods → action demands.** Each method's signature (via
  `prepare_definition`) becomes the arg/return *port matches* the resolved action
  must satisfy.
- **`@declare_state` attributes → state demands.** Each annotated attribute's
  fields become the *port matches* the resolved agent's state must satisfy.

## App + key: how a demand is identified

Every demand carries a **demand target** — the identity of the action/state it
wants to resolve to. The two most important fields are:

- **`app`** — the identifier of the app that provides the action/state
  (e.g. `"imagej"`). Reverse-domain-style, world-unique.
- **`key`** — the action's key within that app (e.g. `"open_image"`), or the
  state's identity key on the agent.

By default these are **inherited from the protocol**:

| Demand | default `app`         | default `key`               |
| ------ | --------------------- | --------------------------- |
| action | the `@declare` app    | the **method name**         |
| state  | the `@declare` app    | the **attribute name**      |

So in the example above `acquire` demands the action `mymicroscope.acquire`, and
`state` demands the state `mymicroscope.state`.

> **Slot key vs. demand key.** The *slot key* is the local name you reference when
> assigning a dependency (the method/attribute name); it always stays stable. The
> *demand key* (inside the demand target) is what gets matched against a remote
> action/state. Overriding the demand target — below — changes what the slot
> resolves to **without** changing how you reference it.

## Demands are suggestions, not hard constraints

A demand is a **hint about the best fit**, not a lock. When your implementation is
set up, the demand's `app` + `key` (and port matches) drive the *default* choice
and the ordering of candidates — but the assigning user always keeps the final
say. They can **opt out and pick a different agent, from a different app**, as long
as it structurally satisfies the slot (its ports match).

When they deviate from what the demand asked for, they are **warned** rather than
blocked: the assignment goes through, but the platform surfaces that the chosen
agent doesn't match the declared `app`/`key`. This keeps declared dependencies
useful as guidance without turning them into a hard allow-list that would break
legitimate substitutions (a different vendor's camera, a fork of an app, a
locally-patched action, …).

### Optional slots

Beyond the assign-time freedom above, a slot can be declared **optional** so a
resolved agent doesn't have to satisfy it at all. Pass `optional=True` to `@demand`
or `demand_state`:

```python
@declare(app="mymicroscope")
class Deps:
    async def acquire(self, exposure_ms: float) -> bytes: ...

    # nice to have — an agent that can't autofocus is still a valid match
    @demand(optional=True)
    async def autofocus(self) -> None: ...

    telemetry: Annotated[TelemetryState, demand_state(optional=True)]
```

An optional slot may be left unfilled at assignment, and an agent that doesn't
implement it is still callable. `optional` composes with a redirect — e.g.
`@demand(app="imagej", key="open_image", optional=True)` demands that foreign
action *when available* but won't block resolution when it isn't.

## Redirecting a single demand — `@demand` and `demand_state`

Sometimes one method or state in a protocol should resolve to an action/state that
does **not** follow the protocol's core app + name. For example, an app implements
a camera protocol but delegates image opening to `imagej`'s `open_image` action.

### Actions — the `@demand` decorator

Decorate the method to override its demand target:

```python
from rekuest_next import declare, demand


@declare(app="mymicroscope")
class Deps:
    # inherits app="mymicroscope", key="acquire"
    async def acquire(self, exposure_ms: float) -> bytes:
        """Acquire a frame."""
        ...

    # redirected: demands imagej.open_image instead of mymicroscope.open
    @demand(app="imagej", key="open_image")
    async def open(self, path: str) -> bytes:
        """Open an image from disk."""
        ...
```

`@demand` accepts:

| argument             | effect                                                                       |
| -------------------- | ---------------------------------------------------------------------------- |
| `app`                | app that provides the action (overrides the inherited protocol app)          |
| `key`                | the action's key within its app (overrides the method name)                  |
| `version`            | pin an exact action version                                                  |
| `hash`               | pin an exact action hash — **short-circuits** matching; everything else ignored |
| `name`               | display name of the action to match                                          |
| `protocols`          | protocols (by name) the resolved action must implement                       |
| `force_arg_length`   | require exactly this many root args                                          |
| `force_return_length`| require exactly this many root returns                                       |
| `match_ports`        | keep emitting the arg/return port matches from the signature (default `True`); set `False` to match purely by `app` + `key` |
| `optional`           | mark this slot optional (default `False`) — an agent that doesn't implement it is still a match, and the slot may be left unfilled |

### States — the `demand_state` marker

States are declared as *annotations*, not methods, so there's nothing to decorate.
Instead, place a `demand_state(...)` marker inside `typing.Annotated`:

```python
from typing import Annotated

from rekuest_next import declare, declare_state, demand_state


@declare_state
class ViewerState:
    open: bool


@declare(app="mymicroscope")
class Deps:
    # inherits app="mymicroscope", key="camera"
    camera: CameraState

    # redirected: demands imagej.viewer_state instead of mymicroscope.viewer
    viewer: Annotated[
        ViewerState, demand_state(app="imagej", key="viewer_state")
    ]
```

`demand_state` accepts `app`, `key`, `hash`, `protocols`, `match_ports`, and
`optional`, with the same semantics as their `@demand` counterparts.

### Pointing at another app narrows resolution to that foreign function

When you override the demand's `app` to something other than your protocol's core
app, you are demanding a **foreign function** — an action (or state) that lives in
a *different* app. Only an agent that actually **implements that foreign action**
can satisfy the slot as a match.

Concretely: `@demand(app="imagej", key="open_image")` means "resolve this slot to
`imagej`'s `open_image` action". An agent is only offered as a matching candidate
for that slot if it implements `imagej.open_image`; agents that merely happen to
expose an `open`-shaped action of their own do **not** count as a match. The
foreign `app` + `key` is the identity the resolver looks for.

This is what makes cross-app delegation safe and precise — you get exactly the
foreign function you named, not an incidental look-alike. (As always, this governs
the *best-fit* candidates; per the note above, the assigning user can still
override the choice and will be warned if they pick something that doesn't
implement the demanded foreign function.)

### When to use an override

- **Delegation.** Your protocol's shape is convenient locally, but the real work
  lives in a well-known action/state of another app.
- **Pinning.** You need a specific `version` or `hash`, not "anything that
  structurally matches".
- **Stand-in signatures.** The local method/attribute is only a placeholder for
  wiring; set `match_ports=False` so matching relies on `app` + `key` alone.

Only the fields you pass are overridden — everything else keeps inheriting. A
`hash`-pinned demand deliberately drops the auto-derived name so it doesn't
over-constrain the match.

## What gets sent to the server

A declared protocol serializes to an `AgentDependencyInput`. Each action/state
demand is a *dependency slot* (`key`, `optional`, `allowInactive`) wrapping a
*demand target*:

```
AgentDependencyInput(
  key="camera_dep",
  app="mymicroscope",
  actionDependencies=[
    ActionDependencyInput(
      key="acquire",                      # slot key (stable, referenced on assign)
      demand=ActionDemandInput(
        app="mymicroscope", key="acquire", # demand target (what it resolves to)
        argMatches=[...], returnMatches=[...],
      ),
    ),
    ActionDependencyInput(
      key="open",
      demand=ActionDemandInput(app="imagej", key="open_image", ...),  # redirected
    ),
  ],
  stateDependencies=[
    StateDependencyInput(
      key="camera",
      demand=StateDemandInput(app="mymicroscope", key="camera", matches=[...]),
    ),
  ],
)
```

The same `demand` targets power query filters too — `ActionDemandInput` /
`StateDemandInput` are used directly by `ActionFilter` / `AgentFilter` to search
for matching actions and agents.

## API reference

| Symbol                                | Import                        |
| ------------------------------------- | ----------------------------- |
| `declare(app=..., ...)`               | `from rekuest_next import declare` |
| `declare_state`                       | `from rekuest_next import declare_state` |
| `demand(*, app=..., key=..., ...)`    | `from rekuest_next import demand` |
| `demand_state(*, app=..., key=..., ...)` | `from rekuest_next import demand_state` |

The override dataclasses (`ActionDemandOverride`, `StateDemandOverride`) and the
low-level builders (`build_action_dependency_input`,
`build_state_dependency_input`) live in `rekuest_next.definition.demands` and
`rekuest_next.definition.dependencies` respectively.
