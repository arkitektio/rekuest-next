# rekuest-next

[![codecov](https://codecov.io/gh/arkitektio/rekuest-next/graph/badge.svg?token=xzxX2AQPmS)](https://codecov.io/gh/arkitektio/rekuest-next)
[![PyPI version](https://badge.fury.io/py/rekuest-next.svg)](https://pypi.org/project/rekuest-next/)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://pypi.org/project/rekuest-next/)
![Maintainer](https://img.shields.io/badge/maintainer-jhnnsrs-blue)
[![PyPI pyversions](https://img.shields.io/pypi/pyversions/rekuest-next.svg)](https://pypi.python.org/pypi/rekuest-next/)
[![PyPI status](https://img.shields.io/pypi/status/rekuest-next.svg)](https://pypi.python.org/pypi/rekuest-next/)

**Self-documenting, asynchronous, scalable RPC for untrusted actors** — accessible
through FastAPI or deployed on the [Arkitekt](https://arkitekt.live) platform.

Turn an ordinary, typed Python function into a remotely callable *action*: rekuest
inspects its signature and docstring to build a self-documenting schema, hosts it as
a provisionable *actor*, and lets other apps discover and call it — with fine-grained,
per-app access control.

## Why rekuest?

Most RPC frameworks expose functionality on a *server*. rekuest flips that around:
functionality lives on the **client**, and any app can *provide* actions on a user's
behalf. That makes it a good fit for scientific and automation workflows where:

- **Code is the contract.** Type hints and docstrings become the schema — args,
  returns, widgets, and documentation are derived automatically, no IDL to maintain.
- **Apps are untrusted.** Every app negotiates access to data and to other apps via
  OAuth2, so you can safely run third-party or user-contributed code.
- **Work is distributed.** Many agents can provide the same action; the platform load
  balances, retries, and fails over calls across them.
- **Calls compose.** An action can call other actions, so you can build pipelines that
  span apps and machines.

## How it works

```
  @register function  ──inspect──▶  Action (self-documenting schema)
        │                                  │
        │ hosted by an Agent               │ discovered + reserved by callers
        ▼                                  ▼
      Actor  ◀───────── assign / call ─────┘
   (running instance,
    expands inputs, runs,
    shrinks outputs)
```

| Term            | Meaning                                                                                   |
| --------------- | ----------------------------------------------------------------------------------------- |
| **Action**      | The documented concept of a function that is available on the platform.                   |
| **Implementation** | A concrete realization of an Action provided by an App.                                |
| **App**         | A provider of functionality that negotiates access rights through OAuth2.                  |
| **Agent**       | A running instance of an App; the host of actors. Agents connect and disconnect.          |
| **Actor**       | A provisioned, running instance of a function that processes assignments.                 |
| **Provision**   | A contract obliging an Agent to keep an action available (think *Deployment* in K8s).     |
| **Reservation** | A contract for a user to call one or more actors; the platform load balances and heals it. |

## Prerequisites

A running rekuest server (most easily obtained through an
[Arkitekt](https://arkitekt.live) deployment).

## Install

rekuest-next is usually consumed through the Arkitekt platform, which wires up the
server connection, authentication and lifecycle for you. Installing `arkitekt-next`
pulls in `rekuest-next` as well:

```bash
pip install arkitekt-next
```

> Doing image analysis? The Arkitekt platform ships ready-made data structures for
> imaging (see [mikro](https://github.com/arkitektio/mikro-next)).

## Providing an action

Register a typed function — its signature and docstring become the schema:

```python
from arkitekt_next import register, easy


@register
def add_greeting(x: int, name: str) -> str:
    """Add a greeting.

    Takes a number and a name and returns a friendly message.

    Args:
        x (int): A number to include in the message.
        name (str): The name to greet.

    Returns:
        str: The greeting message.
    """
    return f"Hello {name}, your number is {x}"


with easy("my_app") as app:
    # Connects, registers the action, and provides it until interrupted.
    app.run()
```

Run it during development with:

```bash
arkitekt-next run dev
```

The action is now registered under your app and signed-in user, and can be
provisioned and called by other apps. By default users may only assign to their own
apps; this can be relaxed on the rekuest server.

## Calling an action

Resolve an action with `find` (by its id, or pass an `Action` straight through), then
invoke it with `call` (sync) or `acall` (async):

```python
from arkitekt_next import easy
from rekuest_next import find, call


with easy("my_app") as app:
    action = find(action_id)            # action_id discovered via search / the platform

    result = call(action, x=1, name="world")
    print(result)                       # "Hello world, your number is 1"
```

When you already know which agent provides an implementation, you can address it
directly and await the result:

```python
from rekuest_next.api.schema import amy_implementation_at
from rekuest_next.remote import acall

impl = await amy_implementation_at(instance_id, "add_greeting")
result = await acall(impl, x=1, name="world")
```

## Working with complex data structures

rekuest serializes and documents the standard Python types out of the box:

`str` · `bool` · `int` · `float` · `Enum` · `dict` · `list`

Large or complex objects (e.g. numpy arrays) should **not** be serialized into
messages. rekuest offers two strategies instead.

### Global structures — reference-by-id

Store the object in central storage and pass only a reference. Make a class a
*structure* with the `@structure` decorator — give it an identifier and async
`ashrink`/`aexpand` methods:

```python
from rekuest_next import structure


@structure(identifier="myapp/image")
class Image:
    id: str  # a reference to this object in central storage

    async def ashrink(self) -> str:
        return self.id

    @classmethod
    async def aexpand(cls, value: str) -> "Image":
        return await cls.load_from_server(value)
```

> The decorator registers the structure eagerly. A class that instead implements a
> `get_identifier()` classmethod alongside `ashrink`/`aexpand` is still picked up
> automatically the first time it is used in a type hint.

Now you can use `Image` directly in type hints — rekuest automatically `ashrink`s
(serializes) it to its reference when sending and `aexpand`s (deserializes) it back on
the receiving side:

```python
@register
def brightest_pixel(image: Image) -> int:
    return image.max()
```

### Memory structures — keep it on the shelve

Sometimes an object only makes sense within the agent that produced it and never needs
to leave the machine — a handle to an open file, a live model, an intermediate result.
Any plain class with no serialization protocol is treated as a **memory structure**:
instead of being serialized, it is parked on the agent's in-memory *shelve*, and only
an opaque *drawer reference* travels on the wire.

```python
class Session:  # no get_identifier / ashrink / aexpand -> memory structure
    def __init__(self, handle):
        self.handle = handle


@register
def open_session(path: str) -> Session:
    return Session(open(path))


@register
def read_session(session: Session) -> str:
    return session.handle.read()
```

Because the object stays on the agent's shelve, piping the reference returned by
`open_session` into `read_session` resolves the **same live object** — no copy, no
re-serialization. See `tests/test_app_memory_structure.py` for end-to-end examples.

## State

Actions are stateless by default — each call is independent. When an agent needs to
remember something *across* calls (a connection, a counter, a loaded model), declare an
**observable state** with `@state` on a dataclass:

```python
from dataclasses import dataclass
from rekuest_next import state, startup


@state
@dataclass
class CounterState:
    count: int = 0


@startup
def initialize() -> CounterState:
    # Startup hooks return the initial state instances for the agent.
    return CounterState(count=0)
```

Any action can then read and mutate that state simply by **type-hinting a parameter**
with the state class — rekuest injects the live instance:

```python
@register
def increment(counter: CounterState) -> int:
    counter.count += 1   # mutation is published to the platform automatically
    return counter.count
```

State is shared by all of an agent's actors and is *observable*: changes are published
live (at `publish_interval`), so dashboards and other apps can watch it in real time. Use
`@state(local_only=True)` to keep a state on the agent without exposing it to the platform.

## Dependencies

An action can call out to functionality provided by **another** agent. You describe what
you need with a **dependency protocol** — `@declare` (a.k.a. `agent_protocol`) inspects the
class so that its public methods become *action demands* and its `@declare_state`
attributes become *state demands*:

```python
from rekuest_next import declare, declare_state


@declare_state
class CameraState:
    connected: bool


@declare(app="lab")
class Camera:
    state: CameraState

    async def snap(self, exposure_ms: float) -> bytes:
        ...   # body is only a signature — it is fulfilled by a remote agent
```

Consume the dependency by type-hinting a parameter with the protocol class. rekuest
resolves a matching remote agent and injects a proxy you can call — `.call(...)`
(sync) or `.acall(...)` (async). Calls are routed through your agent and tracked as
children of the current assignment:

```python
@register
def capture(camera: Camera) -> bytes:
    # Calls the remote agent's `snap` action and returns its result.
    return camera.snap(exposure_ms=10.0)
```

The platform load balances across matching agents and will heal the reservation if one
disconnects. Use `auto_resolvable=True`, `min=`, and `max=` on `@declare` to control how
many matching agents may be bound automatically.

## Bloks — dashboards from JSX

A **blok** is a declarative UI panel an app contributes to the platform — a small
dashboard built from a component tree, wired straight to your actions and state. You
write it as a JSX/XML string; `jsx(...)` parses it into a component tree (with helpful
line/column errors when it can't):

```python
from rekuest_next import jsx

panel = jsx(
    """
    <Page>
      <Label text="Camera" />
      <Text value="$state.camera.connected" />
      <Button title="Snap" onClick="@camera.snap(exposure_ms=10)" />
    </Page>
    """
)

app.register_blok(name="camera_panel", component=panel, description="Camera dashboard")
```

Props follow three conventions, which is what ties a blok to the rest of your app:

| Prop value          | Meaning                                                                 |
| ------------------- | ----------------------------------------------------------------------- |
| `text="Camera"`     | A **static** value.                                                      |
| `value="$state.camera.connected"` | A **dynamic binding** to a dependency's state (`$state.<dependency>.<path>`). |
| `onClick="@camera.snap(exposure_ms=10)"` | An **action callback** that calls a dependency's action (`@<dependency>.<operation>(...)`). Use `@utils.<op>(...)` for built-in utilities. |

Bloks derive their action and state dependencies automatically from the paths they
reference, so the platform knows exactly what each panel needs to run.

## Development

```bash
uv sync                       # install dependencies
pytest -m "not integration"   # fast unit tests
pytest -m integration         # full integration tests (require Docker)
```

Integration tests spin up the rekuest stack with Docker Compose and exercise real
calls against it; see `tests/conftest.py`.

## Learn more

- [Arkitekt platform](https://arkitekt.live)
- [Documentation](https://arkitekt.live/docs)
