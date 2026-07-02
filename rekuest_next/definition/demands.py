"""The ``demand`` decorator for agent-dependency protocol methods.

A method on a :func:`~rekuest_next.declare.declare` protocol becomes an *action
demand*. By default that demand inherits its ``app`` from the protocol's core
app and its ``key`` from the method name. Applying :func:`demand` to a method
overrides that identity — letting a single method point at *another* action
(a different ``app`` + ``key``, version, hash, ...) instead of inheriting it.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Any, Callable, TypeVar, get_args, get_origin

ACTION_DEMAND_ATTR = "__rekuest_action_demand__"
STATE_DEMAND_ATTR = "__rekuest_state_demand__"


@dataclass(frozen=True)
class ActionDemandOverride:
    """Overrides for the action a protocol method demands.

    Every field defaults to ``None`` meaning "inherit / do not override". Fields
    left unset keep the default behaviour (``app`` from the protocol, ``key``
    from the method name, structural port matching).
    """

    app: str | None = None
    key: str | None = None
    version: str | None = None
    hash: str | None = None
    name: str | None = None
    protocols: tuple[str, ...] | None = None
    force_arg_length: int | None = None
    force_return_length: int | None = None
    match_ports: bool = True
    optional: bool = False


F = TypeVar("F", bound=Callable[..., object])


def demand(
    *,
    app: str | None = None,
    key: str | None = None,
    version: str | None = None,
    hash: str | None = None,
    name: str | None = None,
    protocols: Sequence[str] | None = None,
    force_arg_length: int | None = None,
    force_return_length: int | None = None,
    match_ports: bool = True,
    optional: bool = False,
) -> Callable[[F], F]:
    """Override the action an agent-dependency protocol method demands.

    Attach to a method of a :func:`~rekuest_next.declare.declare` protocol to
    redirect its demand to another action — specifying the demanded ``app`` +
    ``key`` (and optional version/hash/protocols) explicitly instead of
    inheriting them from the protocol's core app and the method name.

    Args:
        app: The app that provides the demanded action. Overrides the app the
            method would otherwise inherit from the protocol.
        key: The action's key within its app. Overrides the method name.
        version: Pin an exact action version.
        hash: Pin an exact action hash. When set, matching short-circuits on the
            hash and everything else is ignored.
        name: The display name of the action to match.
        protocols: Protocols (by name) the resolved action must implement.
        force_arg_length: Require the action to have exactly this many root args.
        force_return_length: Require the action to have exactly this many root
            returns.
        match_ports: Whether to still emit the arg/return port matches derived
            from the method signature. Set ``False`` to match purely by
            ``app`` + ``key`` (useful when the local signature is only a stand-in).
        optional: Mark this action slot optional. A resolved agent then does not
            have to implement it to be potentially callable, and the slot may be
            left unfilled at assignment.

    Returns:
        A decorator that annotates the method with the override metadata.

    Examples:
        Redirect a single method to another app's action::

            @declare(app="myapp")
            class Deps:
                # inherits app="myapp", key="acquire"
                async def acquire(self, exposure: float) -> bytes: ...

                # demands imagej.open_image instead of myapp.open
                @demand(app="imagej", key="open_image")
                async def open(self, path: str) -> bytes: ...
    """
    override = ActionDemandOverride(
        app=app,
        key=key,
        version=version,
        hash=hash,
        name=name,
        protocols=tuple(protocols) if protocols is not None else None,
        force_arg_length=force_arg_length,
        force_return_length=force_return_length,
        match_ports=match_ports,
        optional=optional,
    )

    def decorator(method: F) -> F:
        setattr(method, ACTION_DEMAND_ATTR, override)
        return method

    return decorator


def get_action_demand_override(method: object) -> ActionDemandOverride | None:
    """Return the :class:`ActionDemandOverride` attached to ``method``, if any."""
    return getattr(method, ACTION_DEMAND_ATTR, None)


@dataclass(frozen=True)
class StateDemandOverride:
    """Overrides for the state a protocol attribute demands.

    The state analogue of :class:`ActionDemandOverride`. Every field defaults to
    ``None`` meaning "inherit / do not override": ``app`` from the protocol,
    ``key`` from the attribute name, structural port matching on.
    """

    app: str | None = None
    key: str | None = None
    hash: str | None = None
    protocols: tuple[str, ...] | None = None
    match_ports: bool = True
    optional: bool = False


def demand_state(
    *,
    app: str | None = None,
    key: str | None = None,
    hash: str | None = None,
    protocols: Sequence[str] | None = None,
    match_ports: bool = True,
    optional: bool = False,
) -> StateDemandOverride:
    """Override the state an agent-dependency protocol attribute demands.

    States are declared as annotated attributes rather than methods, so — unlike
    :func:`demand` — this returns a marker to place inside :data:`typing.Annotated`
    (it can also be attached to a state class, taking effect wherever that class
    is used). It redirects a state demand to another state — a different ``app``
    + ``key`` — instead of inheriting them from the protocol's core app and the
    attribute name.

    Args:
        app: The app that provides the demanded state. Overrides the app the
            attribute would otherwise inherit from the protocol.
        key: The state's identity key on the agent. Overrides the attribute name.
        hash: Pin an exact state-definition hash. When set, matching
            short-circuits on the hash.
        protocols: Protocols (by name) the resolved state must implement.
        match_ports: Whether to still emit the port matches derived from the
            state definition. Set ``False`` to match purely by ``app`` + ``key``.
        optional: Mark this state slot optional. A resolved agent then does not
            have to expose it to be potentially callable, and the slot may be left
            unfilled at assignment.

    Returns:
        A :class:`StateDemandOverride` marker.

    Examples:
        Redirect a state attribute to another app's state::

            @declare(app="myapp")
            class Deps:
                # inherits app="myapp", key="camera"
                camera: CameraState

                # demands imagej.viewer_state instead of myapp.viewer
                viewer: Annotated[
                    ViewerState, demand_state(app="imagej", key="viewer_state")
                ]
    """
    return StateDemandOverride(
        app=app,
        key=key,
        hash=hash,
        protocols=tuple(protocols) if protocols is not None else None,
        match_ports=match_ports,
        optional=optional,
    )


def unwrap_annotated(annotation: Any) -> Any:
    """Return the underlying type of an ``Annotated[...]`` hint (else the hint)."""
    if get_origin(annotation) is Annotated:
        return get_args(annotation)[0]
    return annotation


def get_state_demand_override(annotation: Any) -> StateDemandOverride | None:
    """Return the :class:`StateDemandOverride` for a state annotation, if any.

    Looks first at ``Annotated[...]`` metadata on the attribute, then falls back
    to a marker attached to the (unwrapped) state class itself.
    """
    if get_origin(annotation) is Annotated:
        for meta in get_args(annotation)[1:]:
            if isinstance(meta, StateDemandOverride):
                return meta
    return getattr(unwrap_annotated(annotation), STATE_DEMAND_ATTR, None)
