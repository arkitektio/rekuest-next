"""Remote-call helpers for rekuest_next.

The public surface is ``acall``/``call`` (single result), ``aiterate``/``iterate``
(streaming), their ``*_raw`` counterparts operating on already-serialized
payloads, and ``acall_dependency``/``call_dependency`` for dependency method
calls. All of them funnel through the same internal helpers: target
resolution, ``AssignInput`` construction, and the postman event stream.
"""

import uuid
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    Generator,
    List,
    Optional,
    Tuple,
    Union,
)

from rekuest_next.api.schema import DefinitionInput
from koil import unkoil, unkoil_gen
from rath.scalars import ID
from rekuest_next.actors.context import useAssign
from rekuest_next.actors.vars import (
    NotWithinATaskError,
)
from rekuest_next.api.schema import (
    TaskEventKind,
    AssignInput,
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
    action_implementation_res: Union[ID, Action, Implementation],
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
    action_implementation_res: Union[
        ID,
        Action,
        Implementation,
    ],
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
    target: Union[Action, Implementation],
) -> Tuple[Action, Optional[Implementation]]:
    """Resolve an action-like target into (action, implementation)."""
    if isinstance(target, Implementation):
        return target.action, target
    if isinstance(target, Action):
        return target, None
    raise ValueError(
        "action_implementation_res must be a Action or Implementation"
    )


def _resolve_postman(postman: Optional[Postman]) -> Postman:
    """Resolve the postman to use, falling back to the current context."""
    postman = postman or get_current_postman()
    if not postman:
        raise ValueError("Postman is not set")
    return postman


def _build_assign_input(
    *,
    args: Optional[Dict[str, Any]],
    reference: Optional[str],
    hooks: Optional[List[HookInput]],
    parent: Optional[Assign],
    cached: bool,
    log: bool,
    capture: bool,
    action: Optional[Action] = None,
    implementation: Optional[Implementation] = None,
    dependency: Optional[ID] = None,
    method: Optional[str] = None,
) -> AssignInput:
    """Build the AssignInput for a remote call.

    When no ``parent`` is given and the call happens inside another
    task, the current task is attached as the parent.
    """
    if parent is None:
        try:
            parent = useAssign()
        except NotWithinATaskError:
            parent = None

    return AssignInput(
        action=action.id if action else None,
        implementation=implementation.id if implementation else None,
        dependency=dependency,
        method=method,  # type: ignore
        args=args or {},
        reference=reference or str(uuid.uuid4()),
        hooks=tuple(hooks or []),
        cached=cached,
        capture=capture,
        parent=ID.validate(parent.task) if parent else None,
        log=log,
        isHook=False,
        ephemeral=False,
    )


async def _astream_raw(
    postman: Postman,
    assign_input: AssignInput,
    escalate_to_interrupt: bool = False,
    cancel_timeout: Optional[float] = None,
) -> AsyncGenerator[Any, None]:
    """Stream the YIELD payloads of a task, returning on DONE.

    Raises:
        ErrorCallError: If the backend reports a task error.
        CriticalCallError: If the backend reports a critical task error.
    """
    async for i in postman.aassign(
        assign_input,
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
    kwargs: Dict[str, Any] | None = None,
    action: Optional[Action] = None,
    implementation: Optional[Implementation] = None,
    parent: Optional[Assign] = None,
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    capture: bool = False,
    log: bool = False,
    postman: Optional[Postman] = None,
    escalate_to_interrupt: bool = False,
    cancel_timeout: Optional[float] = None,
) -> AsyncGenerator[Any, None]:
    """Stream the raw YIELD payloads of a remote call.

    Operates on already-serialized arguments and yields transport-level
    payloads; prefer :func:`aiterate` unless you are deliberately operating on
    transport-level data.
    """
    resolved_postman = _resolve_postman(postman)
    assign_input = _build_assign_input(
        args=kwargs,
        reference=reference,
        hooks=hooks,
        parent=parent,
        cached=cached,
        log=log,
        capture=capture,
        action=action,
        implementation=implementation,
    )

    async for returns in _astream_raw(
        resolved_postman,
        assign_input,
        escalate_to_interrupt=escalate_to_interrupt,
        cancel_timeout=cancel_timeout,
    ):
        yield returns


async def acall_raw(
    kwargs: Dict[str, Any] | None = None,
    action: Optional[Action] = None,
    implementation: Optional[Implementation] = None,
    parent: Optional[Assign] = None,
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    capture: bool = False,
    log: bool = False,
    postman: Optional[Postman] = None,
    escalate_to_interrupt: bool = False,
    cancel_timeout: Optional[float] = None,
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
    returns = tuple()

    async for r in aiterate_raw(
        kwargs=kwargs,
        action=action,
        implementation=implementation,
        parent=parent,
        reference=reference,
        hooks=hooks,
        cached=cached,
        capture=capture,
        log=log,
        postman=postman,
        escalate_to_interrupt=escalate_to_interrupt,
        cancel_timeout=cancel_timeout,
    ):
        returns = r

    return returns


async def acall_dependency_raw(
    dependency_key: ID,
    method: str,
    kwargs: Dict[str, JSONSerializable],
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    parent: Optional[Assign] = None,
    capture: bool = False,
    log: bool = False,
    postman: Optional[Postman] = None,
) -> Any:  # noqa: ANN401
    """Call a method on a dependency with already serialized arguments."""
    resolved_postman = _resolve_postman(postman)
    assign_input = _build_assign_input(
        args=kwargs,
        reference=reference,
        hooks=hooks,
        parent=parent,
        cached=cached,
        log=log,
        capture=capture,
        dependency=dependency_key,
        method=method,
    )

    returns = tuple()

    async for r in _astream_raw(resolved_postman, assign_input):
        returns = r

    return returns


async def acall(
    action_implementation_res: Union[Action, Implementation],
    *args: Any,  # noqa: ANN401
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    parent: Assign | None = None,
    log: bool = False,
    capture: bool = False,
    structure_registry: Optional[StructureRegistry] = None,
    postman: Optional[Postman] = None,
    escalate_to_interrupt: bool = False,
    cancel_timeout: Optional[float] = None,
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

    raw_returns = await acall_raw(
        kwargs=shrinked_args,
        action=action,
        implementation=implementation,
        reference=reference,
        hooks=hooks,
        cached=cached,
        capture=capture,
        parent=parent,
        log=log,
        postman=postman,
        escalate_to_interrupt=escalate_to_interrupt,
        cancel_timeout=cancel_timeout,
    )

    returns = await aexpand_returns(
        action, raw_returns, structure_registry=structure_registry
    )
    if len(returns) == 1:
        return returns[0]
    return returns


async def aiterate(
    action_implementation_res: Union[Action, Implementation],
    *args: Any,  # noqa: ANN401
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    parent: Assign | None = None,
    log: bool = False,
    capture: bool = False,
    structure_registry: Optional[StructureRegistry] = None,
    postman: Optional[Postman] = None,
    escalate_to_interrupt: bool = False,
    cancel_timeout: Optional[float] = None,
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

    async for raw_returns in aiterate_raw(
        kwargs=shrinked_args,
        action=action,
        implementation=implementation,
        reference=reference,
        hooks=hooks,
        cached=cached,
        capture=capture,
        parent=parent,
        log=log,
        postman=postman,
        escalate_to_interrupt=escalate_to_interrupt,
        cancel_timeout=cancel_timeout,
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
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    parent: Assign | None = None,
    capture: bool = False,
    log: bool = False,
    structure_registry: Optional[StructureRegistry] = None,
    postman: Optional[Postman] = None,
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
