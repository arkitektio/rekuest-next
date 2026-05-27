"""General utils for rekuest_next"""

import uuid
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    Generator,
    List,
    Optional,
    Union,
)

from rekuest_next.api.schema import DefinitionInput
from koil import unkoil, unkoil_gen
from rath.scalars import ID
from rekuest_next.actors.context import useAssign
from rekuest_next.actors.vars import (
    NotWithinAnAssignationError,
)
from rekuest_next.api.schema import (
    AssignationEvent,
    AssignationEventKind,
    AssignInput,
    HookInput,
    Action,
    afind as afind_node,
    Reservation,
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
    action_implementation_res: Union[ID, Action, Implementation, Reservation],
) -> Action:
    """Find and return the assignation generator"""
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
        "action_implementation_res must be an ID, Action, Implementation, Reservation, DeclaredFunction or DeclaredProtocol"
    )


def find(
    action_implementation_res: Union[
        ID,
        Action,
        Implementation,
        Reservation,
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


async def acall_dependency_raw(
    dependency_key: ID,
    method: str,
    kwargs: Dict[str, JSONSerializable],  # noqa: ANN401
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    parent: Optional[Assign] = None,
    capture: bool = False,
    log: bool = False,
    postman: Optional[Postman] = None,
) -> Any:  # noqa: ANN002, ANN003, ANN401
    """Call a method on a dependency"""

    """Call the assignation function"""
    postman = postman or get_current_postman()
    if not postman:
        raise ValueError("Postman is not set")

    try:
        parent = useAssign()
    except NotWithinAnAssignationError:
        # If we are not within an assignation, we can set the parent to None
        parent = None

    reference = reference or str(uuid.uuid4())

    x = AssignInput(
        instanceId=postman.instance_id,
        dependency=dependency_key,
        method=method,  # type: ignore
        args=kwargs or {},
        reference=reference,
        hooks=tuple(hooks or []),
        cached=cached,
        capture=capture,
        parent=ID.validate(parent.assignation) if parent else None,
        log=log,
        isHook=False,
        ephemeral=False,
    )

    returns = tuple()

    async for i in postman.aassign(x):
        if i.kind == AssignationEventKind.YIELD:
            returns = i.returns

        if i.kind == AssignationEventKind.DONE:
            return returns

        if i.kind == AssignationEventKind.ERROR:
            raise ErrorCallError(i.message)

        if i.kind == AssignationEventKind.CRITICAL:
            raise CriticalCallError(i.message)


async def acall_raw(
    kwargs: Dict[str, Any] | None = None,
    action: Optional[Action] = None,
    implementation: Optional[Implementation] = None,
    parent: Optional[Assign] = None,
    reservation: Optional[Reservation] = None,
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    capture: bool = False,
    assign_timeout: Optional[float] = None,
    timeout_is_recoverable: bool = False,
    log: bool = False,
    postman: Optional[Postman] = None,
) -> Any:  # noqa: ANN401
    """Execute a low-level remote call with already serialized arguments.

    This helper builds an :class:`AssignInput`, sends it through the current
    postman, and returns the raw backend return payload from the final ``DONE``
    event. It does not shrink Python arguments or expand returned structures;
    prefer :func:`acall` unless you are deliberately operating on transport-level
    payloads.

    If the call happens inside another assignation, the current assignation is
    attached automatically as the parent reference.

    Args:
        kwargs: Already serialized argument payload to send.
        action: Concrete action to execute.
        implementation: Specific implementation override for the action.
        parent: Optional parent assignation. When omitted, the current
            assignation is used if available.
        reservation: Reservation to target instead of a direct action.
        reference: Stable client-side reference for deduplicating or tracking
            the remote call.
        hooks: Hook inputs to attach to the assignation request.
        cached: Whether the backend may reuse cached results.
        capture: Whether the backend should capture outputs for later retrieval.
        assign_timeout: Reserved for compatibility; not currently applied in
            this helper.
        timeout_is_recoverable: Reserved for compatibility; not currently used.
        log: Whether the backend should persist assignation logs.
        postman: Postman override. Defaults to the current postman context.

    Returns:
        The raw return payload emitted by the backend.

    Raises:
        ValueError: If no postman is available.
        ErrorCallError: If the backend reports a recoverable assignation error.
        CriticalCallError: If the backend reports a critical assignation error.

    Examples:
        Send an already serialized payload directly::

            raw_returns = await acall_raw(
                action=action,
                kwargs={"value": 1},
                cached=True,
            )
    """
    postman = postman or get_current_postman()
    if not postman:
        raise ValueError("Postman is not set")

    try:
        parent = useAssign()
    except NotWithinAnAssignationError:
        # If we are not within an assignation, we can set the parent to None
        parent = None

    reference = reference or str(uuid.uuid4())

    x = AssignInput(
        instanceId=postman.instance_id,
        action=action.id if action else None,
        implementation=implementation.id if implementation else None,
        reservation=reservation,  # type: ignore
        args=kwargs or {},
        reference=reference,
        hooks=tuple(hooks or []),
        cached=cached,
        capture=capture,
        parent=ID.validate(parent.assignation) if parent else None,
        log=log,
        isHook=False,
        ephemeral=False,
    )

    returns = tuple()

    async for i in postman.aassign(x):
        if i.kind == AssignationEventKind.YIELD:
            returns = i.returns

        if i.kind == AssignationEventKind.DONE:
            return returns

        if i.kind == AssignationEventKind.ERROR:
            raise ErrorCallError(i.message)

        if i.kind == AssignationEventKind.CRITICAL:
            raise CriticalCallError(i.message)


async def aiterate_raw(
    kwargs: Dict[str, Any] | None = None,
    action: Optional[Action] = None,
    implementation: Optional[Implementation] = None,
    parent: Optional[Assign] = None,
    reservation: Optional[Reservation] = None,
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    capture: bool = False,
    assign_timeout: Optional[float] = None,
    timeout_is_recoverable: bool = False,
    log: bool = False,
    postman: Optional[Postman] = None,
) -> AsyncGenerator[AssignationEvent, None]:
    """Async generator that yields the results of the assignation"""
    postman = postman or get_current_postman()
    if not postman:
        raise ValueError("Postman is not set")

    try:
        parent = useAssign()
    except NotWithinAnAssignationError:
        # If we are not within an assignation, we can set the parent to None
        parent = None

    reference = reference or str(uuid.uuid4())

    x = AssignInput(
        instanceId=postman.instance_id,
        action=action.id if action else None,
        implementation=implementation.id if implementation else None,
        reservation=reservation,  # type: ignore
        args=kwargs or {},
        reference=reference,
        hooks=tuple(hooks or []),
        cached=cached,
        capture=capture,
        parent=ID.validate(parent.assignation) if parent else None,
        log=log,
        isHook=False,
        ephemeral=False,
    )

    async for i in postman.aassign(x):
        if i.kind == AssignationEventKind.YIELD:
            yield i.returns

        if i.kind == AssignationEventKind.DONE:
            return

        if i.kind == AssignationEventKind.ERROR:
            raise ErrorCallError(i.message)

        if i.kind == AssignationEventKind.CRITICAL:
            raise CriticalCallError(i.message)


async def acall(
    action_implementation_res: Union[Action, Implementation, Reservation],
    *args: Any,  # noqa: ANN401
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    parent: Assign | None = None,
    log: bool = False,
    capture: bool = False,
    structure_registry: Optional[StructureRegistry] = None,
    postman: Optional[Postman] = None,
    **kwargs: Any,  # noqa: ANN401
) -> Any:
    """Execute a remote action and return expanded Python values.

    The helper accepts an :class:`Action`, :class:`Implementation`, or
    :class:`Reservation`. It resolves the target action, shrinks Python
    arguments with the active structure registry, performs the remote call via
    :func:`acall_raw`, and expands the returned transport payload back into
    Python objects.

    Single-value returns are unwrapped for convenience. Multiple returns are
    returned as a tuple.

    Args:
        action_implementation_res: Action-like target to execute.
        *args: Positional Python arguments matching the action definition.
        reference: Optional client-side reference for the assignation.
        hooks: Hook inputs to attach to the assignation.
        cached: Whether cached results may be reused.
        parent: Optional parent assignation.
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
        ValueError: If the target object is not an action, implementation, or
            reservation.
        ErrorCallError: If the backend reports an assignation error.
        CriticalCallError: If the backend reports a critical assignation error.

    Examples:
        Call an action asynchronously and receive expanded Python objects::

            result = await acall(action, image=my_image, threshold=0.5)
    """
    action = None
    implementation = None
    reservation = None

    if isinstance(action_implementation_res, Implementation):
        # If the action is a implementation, we need to find the action
        action = action_implementation_res.action
        implementation = action_implementation_res

    elif isinstance(action_implementation_res, Reservation):
        # If the action is a reservation, we need to find the action
        action = action_implementation_res.action
        reservation = action_implementation_res

    elif isinstance(action_implementation_res, Action):  # type: ignore
        # If the action is a action, we need to find the action
        action = action_implementation_res
    else:
        # If the action is not a action, we need to find the action
        raise ValueError(
            "action_implementation_res must be a Action, Implementation or Reservation"
        )

    structure_registry = get_default_structure_registry()

    shrinked_args = await ashrink_args(
        action, args, kwargs, structure_registry=structure_registry
    )

    returns = await acall_raw(
        kwargs=shrinked_args,
        action=action,
        implementation=implementation,
        reservation=reservation,
        reference=reference,
        hooks=hooks or [],
        cached=cached,
        capture=capture,
        parent=parent,
        log=log,
        postman=postman,
    )

    returns = await aexpand_returns(
        action, returns, structure_registry=structure_registry
    )
    if len(returns) == 1:
        return returns[0]
    return returns


async def aiterate(
    action_implementation_res: Union[Action, Implementation, Reservation],
    *args: Any,  # noqa: ANN401
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    parent: Assign | None = None,
    log: bool = False,
    capture: bool = False,
    structure_registry: Optional[StructureRegistry] = None,
    **kwargs: Any,  # noqa: ANN401
) -> AsyncGenerator[tuple[Any], None]:
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
        reference: Optional client-side reference for the assignation.
        hooks: Hook inputs to attach to the assignation.
        cached: Whether cached results may be reused.
        parent: Optional parent assignation.
        log: Whether the remote execution should persist logs.
        capture: Whether outputs should be captured remotely.
        structure_registry: Structure registry used for shrinking and expanding
            structured values.
        **kwargs: Keyword Python arguments matching the action definition.

    Yields:
        Expanded yielded values from the remote assignation.

    Raises:
        ValueError: If the target object is not an action, implementation, or
            reservation.
        ErrorCallError: If the backend reports an assignation error.
        CriticalCallError: If the backend reports a critical assignation error.

    Examples:
        Stream intermediate results from a remote generator-like action::

            async for chunk in aiterate(action, prompt="hello"):
                print(chunk)
    """
    action = None
    implementation = None
    reservation = None

    if isinstance(action_implementation_res, Implementation):
        # If the action is a implementation, we need to find the action
        action = action_implementation_res.action
        implementation = action_implementation_res

    elif isinstance(action_implementation_res, Reservation):
        # If the action is a reservation, we need to find the action
        action = action_implementation_res.action
        reservation = action_implementation_res

    elif isinstance(action_implementation_res, Action):  # type: ignore
        # If the action is a action, we need to find the action
        action = action_implementation_res
    else:
        # If the action is not a action, we need to find the action
        raise ValueError(
            "action_implementation_res must be a Action, Implementation or Reservation"
        )

    structure_registry = structure_registry or get_default_structure_registry()

    shrinked_args = await ashrink_args(
        action, args, kwargs, structure_registry=structure_registry
    )

    async for raw_returns in aiterate_raw(
        kwargs=shrinked_args,
        action=action,
        implementation=implementation,
        reservation=reservation,
        reference=reference,
        hooks=hooks or [],
        cached=cached,
        capture=capture,
        parent=parent,
        log=log,
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
) -> Any:  # noqa: ANN002, ANN003, ANN401
    """Call a method on a dependency"""

    structure_registry = structure_registry or get_default_structure_registry()

    shrinked_args = await ashrink_actor_args(
        definition, args, kwargs, structure_registry=structure_registry
    )

    returns = await acall_dependency_raw(
        kwargs=shrinked_args,
        dependency_key=dependency_key,
        method=method,
        reference=reference,
        hooks=hooks or [],
        cached=cached,
        parent=parent,
        capture=capture,
        log=log,
        postman=postman,
    )

    returns = await aexpand_actor_returns(definition, returns, structure_registry)
    if len(returns) == 1:
        return returns[0]
    return returns


def call_dependency(
    definition: DefinitionInput,
    dependency_key: ID,
    method: str,
    *args: Any,  # noqa: ANN401
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    parent: Assign | None = None,
    log: bool = False,
    structure_registry: Optional[StructureRegistry] = None,
    postman: Optional[Postman] = None,
    **kwargs: Any,  # noqa: ANN401
) -> Any:  # noqa: ANN002, ANN003, ANN401
    return unkoil(
        acall_dependency,
        definition,
        dependency_key,
        method,
        *args,
        reference=reference,
        hooks=hooks,
        cached=cached,
        parent=parent,
        log=log,
        structure_registry=structure_registry,
        postman=postman,
        **kwargs,
    )


def call(
    action_implementation_res: Union[Action, Implementation, Reservation],
    *args: Any,  # noqa: ANN401
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    parent: Assign | None = None,
    log: bool = False,
    structure_registry: Optional[StructureRegistry] = None,
    postman: Optional[Postman] = None,
    **kwargs: Any,  # noqa: ANN401
) -> Any:  # noqa: ANN002, ANN003, ANN401
    """Synchronously execute a remote action and return expanded values.

    This is the blocking counterpart to :func:`acall`. It bridges into the async
    implementation via ``unkoil`` so synchronous code can call remote actions
    without managing an event loop explicitly.

    Args:
        action_implementation_res: Action-like target to execute.
        *args: Positional Python arguments matching the action definition.
        reference: Optional client-side reference for the assignation.
        hooks: Hook inputs to attach to the assignation.
        cached: Whether cached results may be reused.
        parent: Optional parent assignation.
        log: Whether the remote execution should persist logs.
        structure_registry: Structure registry used for shrinking and expanding
            structured values.
        postman: Postman override. Defaults to the current postman context.
        **kwargs: Keyword Python arguments matching the action definition.

    Returns:
        The expanded return value, or a tuple of values for multi-return
        actions.

    Examples:
        Call a remote action from synchronous code::

            result = call(action, value=1)
    """
    return unkoil(
        acall,
        action_implementation_res,
        *args,
        reference=reference,
        hooks=hooks,
        cached=cached,
        parent=parent,
        log=log,
        structure_registry=structure_registry,
        postman=postman,
        **kwargs,
    )


def iterate(
    action_implementation_res: Union[Action, Implementation, Reservation],
    *args: Any,  # noqa: ANN401
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    parent: Assign | None = None,
    log: bool = False,
    structure_registry: Optional[StructureRegistry] = None,
    **kwargs: Any,  # noqa: ANN401
) -> Generator[Any, None, None]:
    """Synchronously stream expanded yield values from a remote action.

    This is the blocking counterpart to :func:`aiterate`. It adapts the async
    iterator through ``unkoil_gen`` so synchronous code can consume remote yield
    events without managing an event loop explicitly.

    Args:
        action_implementation_res: Action-like target to execute.
        *args: Positional Python arguments matching the action definition.
        reference: Optional client-side reference for the assignation.
        hooks: Hook inputs to attach to the assignation.
        cached: Whether cached results may be reused.
        parent: Optional parent assignation.
        log: Whether the remote execution should persist logs.
        structure_registry: Structure registry used for shrinking and expanding
            structured values.
        **kwargs: Keyword Python arguments matching the action definition.

    Yields:
        Expanded yielded values from the remote assignation.

    Examples:
        Consume streamed remote results from synchronous code::

            for chunk in iterate(action, prompt="hello"):
                print(chunk)
    """
    return unkoil_gen(
        aiterate,
        action_implementation_res,
        *args,
        reference=reference,
        hooks=hooks,
        cached=cached,
        parent=parent,
        log=log,
        structure_registry=structure_registry,
        **kwargs,
    )
