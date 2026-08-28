"""Remote-call helpers for rekuest_next.

The public surface is ``acall``/``call`` (single result), ``aiterate``/``iterate``
(streaming), their ``*_raw`` counterparts operating on already-serialized
payloads, and ``acall_dependency``/``call_dependency`` for dependency method
calls. All of them funnel through the same internal helpers: target
resolution, ``AssignInput`` construction, and the postman event stream.
"""

import uuid
from dataclasses import dataclass, replace as dc_replace
from typing import (
    Any,
)
from collections.abc import AsyncGenerator, Generator

from rekuest_next.api.schema import DefinitionInput
from koil import unkoil, unkoil_gen
from rath.scalars import ID
from rekuest_next.actors.context import useAssign
from rekuest_next.actors.vars import (
    NotWithinATaskError,
)
from rekuest_next.api.schema import (
    TaskEventKind,
    HookInput,
    Action,
    afind as afind_node,
    Implementation,
)
from rekuest_next.messages import Assign, JSONSerializable
from rekuest_next.postmans.types import Postman
from rekuest_next.postmans.vars import get_current_postman
from rekuest_next.structures.registry import (
    StructureRegistry,
)
from rekuest_next.structures.default import get_default_structure_registry
from rekuest_next.structures.serialization.actor import (
    aexpand_actor_returns,
    ashrink_actor_args,
)
from rekuest_next.structures.serialization.postman import aexpand_returns, ashrink_args
from rekuest_next.errors import CriticalCallError, ErrorCallError


__all__ = [
    "find",
    "afind",
]


async def afind(
    action_implementation_res: ID | Action | Implementation,
) -> Action:
    """Find and return the task generator"""
    if isinstance(action_implementation_res, Action):
        return action_implementation_res

    if isinstance(action_implementation_res, (ID, str)):
        if isinstance(action_implementation_res, str):
            if "." in action_implementation_res:
                # If the ID is a string with dots, we assume it's an app . action identifier, and we need to find the action by its identifier
                raise ValueError(
                    "Finding by string identifier is not supported yet. Please use the ID type for now."
                )

        action_implementation_res = await afind_node(action_implementation_res)
        return action_implementation_res

    raise ValueError(
        "action_implementation_res must be an ID, Action, Implementation, DeclaredFunction or DeclaredProtocol"
    )


def find(
    action_implementation_res: ID | Action | Implementation,
) -> Action:
    """Resolve an action reference into a concrete action model.

    This synchronous helper delegates to :func:`afind` through ``unkoil``. If an
    :class:`Action` is passed, it is returned unchanged. If an id-like value is
    passed, the helper fetches the matching action through the GraphQL layer.

    Args:
        action_implementation_res: Action object or action id to resolve.

    Returns:
        The resolved action model.

    Raises:
        ValueError: If the reference type is unsupported.

    Examples:
        Resolve an action id before calling it::

            action = find(action_id)
            result = call(action, value=1)
    """
    return unkoil(afind, action_implementation_res)


def ensure_return_as_tuple(value: Any) -> tuple[Any]:  # noqa: ANN401
    """Ensure that the value is a list."""
    if not value:
        return tuple()
    if isinstance(value, tuple):
        return value  # type: ignore
    return tuple([value])


def _resolve_target(
    target: Action | Implementation,
) -> tuple[Action, Implementation | None]:
    """Resolve an action-like target into (action, implementation)."""
    if isinstance(target, Implementation):
        return target.action, target
    if isinstance(target, Action):
        return target, None
    raise ValueError("action_implementation_res must be a Action or Implementation")


def _resolve_postman(postman: Postman | None) -> Postman:
    """Resolve the postman to use, falling back to the current context."""
    postman = postman or get_current_postman()
    if not postman:
        raise ValueError("Postman is not set")
    return postman


def _resolve_parent(parent: Assign | None) -> ID | None:
    """The parent task id to attach this call to, as the socket wants it.

    When no ``parent`` is given and the call happens inside another task, the current
    task becomes the parent. Only the agent socket can carry one — which is exactly the
    postman bound while an actor body runs, so the two line up on their own.
    """
    if parent is None:
        try:
            parent = useAssign()
        except NotWithinATaskError:
            return None
    return ID.validate(parent.task)


@dataclass(frozen=True)
class CallOptions:
    """Transport-level options shared by every remote call helper.

    Bundles the parameters that are forwarded unchanged from :func:`acall` /
    :func:`aiterate` down to the postman, so each layer takes one object instead
    of re-listing a dozen keyword arguments.
    """

    reference: str | None = None
    hooks: list[HookInput] | None = None
    capture: bool = False
    parent: Assign | None = None
    postman: Postman | None = None
    escalate_to_interrupt: bool = False
    cancel_timeout: float | None = None


_DEFAULT_OPTIONS = CallOptions()


def _resolve_options(options: CallOptions | None, **overrides: Any) -> CallOptions:  # noqa: ANN401
    """Merge legacy keyword arguments onto an options object.

    Keyword arguments that differ from the ``CallOptions`` defaults win over the
    corresponding field of ``options``; defaults never clobber an explicit option.
    """
    resolved = options or _DEFAULT_OPTIONS
    effective = {
        name: value
        for name, value in overrides.items()
        if value != getattr(_DEFAULT_OPTIONS, name)
    }
    return dc_replace(resolved, **effective) if effective else resolved



async def _astream_raw(  # noqa: PLR0913 - the call description, mirrored from the protocol
    postman: Postman,
    *,
    args: dict[str, Any] | None = None,
    reference: str | None = None,
    hooks: list[HookInput] | None = None,
    capture: bool = False,
    action: Action | None = None,
    implementation: Implementation | None = None,
    parent: ID | None = None,
    dependency: ID | None = None,
    method: str | None = None,
    escalate_to_interrupt: bool = False,
    cancel_timeout: float | None = None,
) -> AsyncGenerator[Any, None]:
    """Stream the YIELD payloads of a task, returning on DONE.

    The call is described by its arguments rather than by a pre-built payload: the
    GraphQL postman and the agent postman no longer share one (see
    :meth:`rekuest_next.postmans.types.Postman.aassign`), so each builds its own.

    Raises:
        ErrorCallError: If the backend reports a task error.
        CriticalCallError: If the backend reports a critical task error.
        RootOnlyAssignError: If a ``parent``/``dependency``/``method`` call is routed
            to a postman that can only create root tasks.
    """
    async for i in postman.aassign(
        args=args or {},
        capture=capture,
        reference=reference or str(uuid.uuid4()),
        hooks=tuple(hooks or []),
        action=action.id if action else None,
        implementation=implementation.id if implementation else None,
        parent=parent,
        dependency=dependency,
        method=method,
        escalate_to_interrupt=escalate_to_interrupt,
        cancel_timeout=cancel_timeout,
    ):
        if i.kind == TaskEventKind.YIELD:
            yield i.returns

        if i.kind == TaskEventKind.COMPLETED:
            return

        if i.kind == TaskEventKind.FAILED:
            raise ErrorCallError(i.message)

        if i.kind == TaskEventKind.CRITICAL:
            raise CriticalCallError(i.message)


async def aiterate_raw(
    kwargs: dict[str, Any] | None = None,
    action: Action | None = None,
    implementation: Implementation | None = None,
    parent: Assign | None = None,
    reference: str | None = None,
    hooks: list[HookInput] | None = None,
    cached: bool = False,
    capture: bool = False,
    log: bool = False,
    postman: Postman | None = None,
    escalate_to_interrupt: bool = False,
    cancel_timeout: float | None = None,
    options: CallOptions | None = None,
) -> AsyncGenerator[Any, None]:
    """Stream the raw YIELD payloads of a remote call.

    Operates on already-serialized arguments and yields transport-level
    payloads; prefer :func:`aiterate` unless you are deliberately operating on
    transport-level data.

    ``cached`` and ``log`` are accepted but not sent: the backend dropped both fields
    from ``AssignInput`` (``cached`` had already been documented there as having no
    effect — replay is decided caller-side via ``reusableTaskFor``). They stay in the
    signature so existing callers keep working. Prefer passing ``options``; the
    individual keyword arguments are merged onto it for backwards compatibility.
    """
    del cached, log  # accepted for compatibility, never sent
    opts = _resolve_options(
        options,
        parent=parent,
        reference=reference,
        hooks=hooks,
        capture=capture,
        postman=postman,
        escalate_to_interrupt=escalate_to_interrupt,
        cancel_timeout=cancel_timeout,
    )
    resolved_postman = _resolve_postman(opts.postman)

    async for returns in _astream_raw(
        resolved_postman,
        args=kwargs,
        reference=opts.reference,
        hooks=opts.hooks,
        capture=opts.capture,
        action=action,
        implementation=implementation,
        parent=_resolve_parent(opts.parent),
        escalate_to_interrupt=opts.escalate_to_interrupt,
        cancel_timeout=opts.cancel_timeout,
    ):
        yield returns


async def acall_raw(
    kwargs: dict[str, Any] | None = None,
    action: Action | None = None,
    implementation: Implementation | None = None,
    parent: Assign | None = None,
    reference: str | None = None,
    hooks: list[HookInput] | None = None,
    cached: bool = False,
    capture: bool = False,
    log: bool = False,
    postman: Postman | None = None,
    escalate_to_interrupt: bool = False,
    cancel_timeout: float | None = None,
    options: CallOptions | None = None,
) -> Any:  # noqa: ANN401
    """Execute a low-level remote call with already serialized arguments.

    Sends a task through the current postman and returns the raw
    backend payload of the final ``YIELD`` event. It does not shrink Python
    arguments or expand returned structures; prefer :func:`acall` unless you
    are deliberately operating on transport-level payloads.

    Raises:
        ValueError: If no postman is available.
        ErrorCallError: If the backend reports a recoverable task error.
        CriticalCallError: If the backend reports a critical task error.
    """
    del cached, log  # accepted for compatibility, never sent
    returns = tuple()

    async for r in aiterate_raw(
        kwargs=kwargs,
        action=action,
        implementation=implementation,
        options=_resolve_options(
            options,
            parent=parent,
            reference=reference,
            hooks=hooks,
            capture=capture,
            postman=postman,
            escalate_to_interrupt=escalate_to_interrupt,
            cancel_timeout=cancel_timeout,
        ),
    ):
        returns = r

    return returns


async def acall_dependency_raw(
    dependency_key: ID,
    method: str,
    kwargs: dict[str, JSONSerializable],
    reference: str | None = None,
    hooks: list[HookInput] | None = None,
    cached: bool = False,
    parent: Assign | None = None,
    capture: bool = False,
    log: bool = False,
    postman: Postman | None = None,
) -> Any:  # noqa: ANN401
    """Call a method on a dependency with already serialized arguments.

    A dependency method call is never a root, so it can only be originated over the
    agent socket — which is the postman bound while an actor body runs. Calling it from
    outside a task raises ``RootOnlyAssignError``.

    ``cached`` and ``log`` are accepted but not sent: the backend dropped both fields
    from ``AssignInput`` (``cached`` had already been documented there as having no
    effect — replay is decided caller-side via ``reusableTaskFor``). They stay in the
    signature so existing callers keep working.
    """
    resolved_postman = _resolve_postman(postman)

    returns = tuple()

    async for r in _astream_raw(
        resolved_postman,
        args=kwargs,
        reference=reference,
        hooks=hooks,
        capture=capture,
        parent=_resolve_parent(parent),
        dependency=dependency_key,
        method=method,
    ):
        returns = r

    return returns


async def acall(
    action_implementation_res: Action | Implementation,
    *args: Any,  # noqa: ANN401
    reference: str | None = None,
    hooks: list[HookInput] | None = None,
    cached: bool = False,
    parent: Assign | None = None,
    log: bool = False,
    capture: bool = False,
    structure_registry: StructureRegistry | None = None,
    postman: Postman | None = None,
    escalate_to_interrupt: bool = False,
    cancel_timeout: float | None = None,
    options: CallOptions | None = None,
    **kwargs: Any,  # noqa: ANN401
) -> Any:
    """Execute a remote action and return expanded Python values.

    The helper accepts an :class:`Action` or :class:`Implementation`. It
    resolves the target action, shrinks Python
    arguments with the structure registry, performs the remote call via
    :func:`acall_raw`, and expands the returned transport payload back into
    Python objects.

    Single-value returns are unwrapped for convenience. Multiple returns are
    returned as a tuple.

    Args:
        action_implementation_res: Action-like target to execute.
        *args: Positional Python arguments matching the action definition.
        reference: Optional client-side reference for the task.
        hooks: Hook inputs to attach to the task.
        cached: Whether cached results may be reused.
        parent: Optional parent task. When omitted, the current
            task is used if available.
        log: Whether the remote execution should persist logs.
        capture: Whether outputs should be captured remotely.
        structure_registry: Structure registry used for shrinking and expanding
            structured values. Defaults to the current default registry.
        postman: Postman override. Defaults to the current postman context.
        **kwargs: Keyword Python arguments matching the action definition.

    Returns:
        The expanded return value, or a tuple of values for multi-return
        actions.

    Raises:
        ValueError: If the target object is not an action or implementation.
        ErrorCallError: If the backend reports a task error.
        CriticalCallError: If the backend reports a critical task error.

    Examples:
        Call an action asynchronously and receive expanded Python objects::

            result = await acall(action, image=my_image, threshold=0.5)
    """
    action, implementation = _resolve_target(action_implementation_res)
    structure_registry = structure_registry or get_default_structure_registry()

    shrinked_args = await ashrink_args(
        action, args, kwargs, structure_registry=structure_registry
    )

    del cached, log  # accepted for compatibility, never sent
    raw_returns = await acall_raw(
        kwargs=shrinked_args,
        action=action,
        implementation=implementation,
        options=_resolve_options(
            options,
            parent=parent,
            reference=reference,
            hooks=hooks,
            capture=capture,
            postman=postman,
            escalate_to_interrupt=escalate_to_interrupt,
            cancel_timeout=cancel_timeout,
        ),
    )

    returns = await aexpand_returns(
        action, raw_returns, structure_registry=structure_registry
    )
    if len(returns) == 1:
        return returns[0]
    return returns


async def aiterate(
    action_implementation_res: Action | Implementation,
    *args: Any,  # noqa: ANN401
    reference: str | None = None,
    hooks: list[HookInput] | None = None,
    cached: bool = False,
    parent: Assign | None = None,
    log: bool = False,
    capture: bool = False,
    structure_registry: StructureRegistry | None = None,
    postman: Postman | None = None,
    escalate_to_interrupt: bool = False,
    cancel_timeout: float | None = None,
    options: CallOptions | None = None,
    **kwargs: Any,  # noqa: ANN401
) -> AsyncGenerator[Any, None]:
    """Stream expanded yield values from a remote action.

    This helper follows the same target-resolution and structure-conversion flow
    as :func:`acall`, but yields each intermediate ``YIELD`` payload from the
    backend as soon as it arrives. Each yield is expanded through the structure
    registry before being exposed to the caller.

    Single-value yields are unwrapped for convenience. Multi-value yields are
    emitted as tuples.

    Args:
        action_implementation_res: Action-like target to execute.
        *args: Positional Python arguments matching the action definition.
        reference: Optional client-side reference for the task.
        hooks: Hook inputs to attach to the task.
        cached: Whether cached results may be reused.
        parent: Optional parent task. When omitted, the current
            task is used if available.
        log: Whether the remote execution should persist logs.
        capture: Whether outputs should be captured remotely.
        structure_registry: Structure registry used for shrinking and expanding
            structured values.
        postman: Postman override. Defaults to the current postman context.
        **kwargs: Keyword Python arguments matching the action definition.

    Yields:
        Expanded yielded values from the remote task.

    Raises:
        ValueError: If the target object is not an action or implementation.
        ErrorCallError: If the backend reports a task error.
        CriticalCallError: If the backend reports a critical task error.

    Examples:
        Stream intermediate results from a remote generator-like action::

            async for chunk in aiterate(action, prompt="hello"):
                print(chunk)
    """
    action, implementation = _resolve_target(action_implementation_res)
    structure_registry = structure_registry or get_default_structure_registry()

    shrinked_args = await ashrink_args(
        action, args, kwargs, structure_registry=structure_registry
    )

    del cached, log  # accepted for compatibility, never sent
    async for raw_returns in aiterate_raw(
        kwargs=shrinked_args,
        action=action,
        implementation=implementation,
        options=_resolve_options(
            options,
            parent=parent,
            reference=reference,
            hooks=hooks,
            capture=capture,
            postman=postman,
            escalate_to_interrupt=escalate_to_interrupt,
            cancel_timeout=cancel_timeout,
        ),
    ):
        returns = await aexpand_returns(
            action, raw_returns, structure_registry=structure_registry
        )
        if len(returns) == 1:
            yield returns[0]
        else:
            yield returns


async def acall_dependency(
    definition: DefinitionInput,
    dependency_key: ID,
    method: str,
    *args: Any,  # noqa: ANN401
    reference: str | None = None,
    hooks: list[HookInput] | None = None,
    cached: bool = False,
    parent: Assign | None = None,
    capture: bool = False,
    log: bool = False,
    structure_registry: StructureRegistry | None = None,
    postman: Postman | None = None,
    **kwargs: Any,  # noqa: ANN401
) -> Any:  # noqa: ANN401
    """Call a method on a dependency and return expanded Python values."""
    structure_registry = structure_registry or get_default_structure_registry()

    shrinked_args = await ashrink_actor_args(
        definition, args, kwargs, structure_registry=structure_registry
    )

    raw_returns = await acall_dependency_raw(
        kwargs=shrinked_args,
        dependency_key=dependency_key,
        method=method,
        reference=reference,
        hooks=hooks,
        cached=cached,
        parent=parent,
        capture=capture,
        log=log,
        postman=postman,
    )

    returns = await aexpand_actor_returns(definition, raw_returns, structure_registry)
    if len(returns) == 1:
        return returns[0]
    return returns


def call(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
    """Synchronously execute a remote action and return expanded values.

    Blocking counterpart to :func:`acall` (see there for parameters); bridges
    into the async implementation via ``unkoil``.
    """
    return unkoil(acall, *args, **kwargs)


def iterate(*args: Any, **kwargs: Any) -> Generator[Any, None, None]:  # noqa: ANN401
    """Synchronously stream expanded yield values from a remote action.

    Blocking counterpart to :func:`aiterate` (see there for parameters);
    adapts the async iterator through ``unkoil_gen``.
    """
    return unkoil_gen(aiterate, *args, **kwargs)


def call_dependency(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
    """Synchronously call a method on a dependency.

    Blocking counterpart to :func:`acall_dependency` (see there for
    parameters).
    """
    return unkoil(acall_dependency, *args, **kwargs)


def call_dependency_raw(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
    """Synchronously call a method on a dependency with already serialized arguments."""
    return unkoil(acall_dependency_raw, *args, **kwargs)


def call_raw(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
    """Synchronously execute a low-level remote call with already serialized arguments."""
    return unkoil(acall_raw, *args, **kwargs)
