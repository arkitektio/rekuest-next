"""Shared helpers for pure port calls (validators and effects).

A port validator or effect carries a blok ``UtilCallInput`` that the UI evaluates
against its function catalog. The server only accepts *pure* calls: no nested
agent calls, and every ``value_path`` must be rooted at ``value`` (the port's own
value) or at a name listed in ``dependencies``. This module is the single walker
over a call's argument tree, used by the authoring helpers (to infer
``dependencies``), by the traits mixed into the generated input models (to reject
impure calls before upload) and by the annotated-types bridge.

It lives under ``traits`` because the generated ``rekuest_next.api.schema`` imports
``rekuest_next.traits.ports`` at import time, so anything imported from a trait
must not itself import the generated module at runtime.
"""

from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING

from rekuest_next.catalogs import base_operation

if TYPE_CHECKING:
    from rekuest_next.api.schema import ActionArgumentInput, UtilCallInput

OWN_VALUE = "value"
"""The reserved ``value_path`` root that refers to the port's own value."""


def value_path_root(value_path: str) -> str:
    """Return the first segment of a JSON-pointer-like value path.

    ``'/other/x'`` -> ``'other'``, ``'other/x'`` -> ``'other'``, ``'value'`` -> ``'value'``.
    Mirrors the server's root extraction exactly.
    """
    return value_path.lstrip("/").split("/", 1)[0]


def iter_call_arguments(call: "UtilCallInput") -> Iterator["ActionArgumentInput"]:
    """Yield every argument node in ``call``, depth first.

    Recurses through nested util calls, agent calls, ``value_list`` and ``value_dict``.
    """

    def walk(arguments: Iterable["ActionArgumentInput"] | None) -> Iterator["ActionArgumentInput"]:
        for argument in arguments or ():
            yield argument
            if argument.util_call is not None:
                yield from walk(argument.util_call.arguments)
            if argument.agent_call is not None:
                yield from walk(argument.agent_call.arguments)
            yield from walk(argument.value_list)
            yield from walk(argument.value_dict)

    yield from walk(call.arguments)


def infer_dependencies(
    call: "UtilCallInput", explicit: Iterable[str] | None = None
) -> tuple[str, ...]:
    """Infer the ports a call subscribes to.

    Every ``value_path`` root in the argument tree except :data:`OWN_VALUE` is a
    dependency, in first-seen order without duplicates. ``explicit`` entries not
    already present are appended, so callers can subscribe to extra ports.
    """
    seen: dict[str, None] = {}
    for argument in iter_call_arguments(call):
        if argument.value_path is None:
            continue
        root = value_path_root(argument.value_path)
        if root and root != OWN_VALUE:
            seen.setdefault(root, None)
    for name in explicit or ():
        seen.setdefault(name, None)
    return tuple(seen)


ARGUMENT_BINDINGS = (
    "value_literal",
    "value_path",
    "agent_call",
    "util_call",
    "value_list",
    "value_dict",
)
"""The mutually exclusive ways an :class:`ActionArgumentInput` can be bound."""


def _check_keyed(arguments: Iterable["ActionArgumentInput"] | None, owner: str) -> None:
    """Map-shaped argument lists (call arguments, ``value_dict``) need unique, non-empty keys."""
    seen: set[str] = set()
    for argument in arguments or ():
        if not argument.key:
            raise ValueError(f"{owner}: every entry must carry a key")
        if argument.key in seen:
            raise ValueError(f"{owner}: duplicate key {argument.key!r}")
        seen.add(argument.key)


def check_call_shape(call: "UtilCallInput", owner: str) -> None:
    """Raise ``ValueError`` unless ``call`` has the argument shape the server accepts.

    Mirrors the server's shape rules: the operation is named, call arguments and
    ``value_dict`` entries carry unique non-empty keys, ``value_list`` entries carry
    no key, and every argument is bound in exactly one way. Nested util calls are
    checked the same way.
    """
    if not call.operation or not call.operation.strip():
        raise ValueError(f"{owner} must name an operation")
    _check_keyed(call.arguments, f"{owner}: arguments of {call.operation}")

    for argument in call.arguments or ():
        bound = [name for name in ARGUMENT_BINDINGS if getattr(argument, name) is not None]
        if len(bound) != 1:
            raise ValueError(
                f"{owner}: argument {argument.key!r} must set exactly one of "
                f"{', '.join(ARGUMENT_BINDINGS)} (got {bound or 'none'})"
            )
        _check_keyed(argument.value_dict, f"{owner}: value_dict of argument {argument.key!r}")
        for entry in argument.value_list or ():
            if entry.key is not None:
                raise ValueError(
                    f"{owner}: value_list entries of argument {argument.key!r} must not carry a key"
                )
        if argument.util_call is not None:
            check_call_shape(argument.util_call, owner)
        for nested in (*(argument.value_list or ()), *(argument.value_dict or ())):
            if nested.util_call is not None:
                check_call_shape(nested.util_call, owner)


def check_pure_call(
    call: "UtilCallInput", dependencies: Iterable[str] | None, owner: str
) -> None:
    """Raise ``ValueError`` unless ``call`` is pure and only references ``dependencies``.

    This is the client-side mirror of the server's rule: the call has a valid
    shape (:func:`check_call_shape`), no agent call may appear anywhere in the
    argument tree, and every ``value_path`` root must be :data:`OWN_VALUE` or
    listed in ``dependencies``. ``owner`` names the validator/effect in error
    messages.
    """
    check_call_shape(call, owner)

    allowed = set(dependencies or ()) | {OWN_VALUE}

    for argument in iter_call_arguments(call):
        if argument.agent_call is not None:
            raise ValueError(f"{owner} must be pure: nested agent calls are not allowed")
        if argument.value_path is not None:
            root = value_path_root(argument.value_path)
            if root not in allowed:
                raise ValueError(
                    f"{owner} references '{root}' via value_path but it is not in dependencies "
                    "(declare it with dependencies=[...], or build the call with "
                    "withValidator/withEffect, which infer it)"
                )


def _is_positional(argument: "ActionArgumentInput") -> bool:
    return argument.key is None or argument.key.isdigit()


def resolve_base_arguments(
    operation: str, arguments: Iterable["ActionArgumentInput"], owner: str
) -> list["ActionArgumentInput"]:
    """Name the positional arguments of a base operation.

    Positional entries (index keys ``"0"``, ``"1"``, ... or no key) are mapped onto the
    base operation's parameters in order; keyword entries are checked against them; the
    result is in manifest order. Operations the base catalog does not know are returned
    unchanged (their positional entries keep their index keys for the UI to map).

    Raises:
        ValueError: too many positionals, an unknown keyword, a parameter given twice, or
            a required parameter missing.
    """
    spec = base_operation(operation)
    arguments = list(arguments)
    if spec is None:
        return arguments

    keys = spec.keys
    positional = sorted(
        (a for a in arguments if _is_positional(a)),
        key=lambda a: int(a.key) if a.key is not None else -1,
    )
    named = [a for a in arguments if not _is_positional(a)]

    if len(positional) > len(keys):
        raise ValueError(
            f"{owner}: {operation} takes at most {len(keys)} positional arguments ({', '.join(keys)})"
        )

    resolved: dict[str, "ActionArgumentInput"] = {}
    for index, argument in enumerate(positional):
        resolved[keys[index]] = argument.model_copy(update={"key": keys[index]})
    for argument in named:
        assert argument.key is not None
        if argument.key not in keys:
            raise ValueError(
                f"{owner}: {operation} does not accept argument {argument.key!r} (accepts {', '.join(keys)})"
            )
        if argument.key in resolved:
            raise ValueError(f"{owner}: {operation} got multiple values for {argument.key!r}")
        resolved[argument.key] = argument

    missing = [key for key in spec.required_keys if key not in resolved]
    if missing:
        raise ValueError(f"{owner}: {operation} requires arguments {missing}")

    return [resolved[key] for key in keys if key in resolved]
