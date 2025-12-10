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
    find as find_node,
    afind as afind_node,
    Reservation,
    Implementation,
)
from rekuest_next.messages import Assign
from rekuest_next.postmans.types import Postman
from rekuest_next.postmans.vars import get_current_postman
from rekuest_next.structures.registry import (
    StructureRegistry,
)
from rekuest_next.structures.default import get_default_structure_registry
from rekuest_next.structures.serialization.postman import aexpand_returns, ashrink_args
from typing import TYPE_CHECKING
from rekuest_next.errors import CriticalCallError, ErrorCallError

if TYPE_CHECKING:
    from rekuest_next.declare import DeclaredFunction, DeclaredProtocol


__all__ = [
    "find",
    "afind",
]


async def afind(
    action_implementation_res: Union[
        ID, Action, Implementation, Reservation, "DeclaredFunction", "DeclaredProtocol"
    ],
) -> Action:
    from rekuest_next.declare import DeclaredFunction, DeclaredProtocol

    """Find and return the assignation generator"""
    if isinstance(action_implementation_res, Action):
        return action_implementation_res

    if isinstance(action_implementation_res, (ID, str)):
        action_implementation_res = await afind_node(action_implementation_res)
        return action_implementation_res

    if isinstance(action_implementation_res, (DeclaredFunction, DeclaredProtocol)):
        action_implementation_res = await afind_node(
            matching=action_implementation_res.to_dependency_input()
        )
        return action_implementation_res

    raise ValueError(
        "action_implementation_res must be an ID, Action, Implementation, Reservation, DeclaredFunction or DeclaredProtocol"
    )


def find(
    action_implementation_res: Union[
        ID, Action, Implementation, Reservation, "DeclaredFunction", "DeclaredProtocol"
    ],
) -> Action:
    return unkoil(afind, action_implementation_res)


def ensure_return_as_tuple(value: Any) -> tuple[Any]:  # noqa: ANN401
    """Ensure that the value is a list."""
    if not value:
        return tuple()
    if isinstance(value, tuple):
        return value  # type: ignore
    return tuple([value])


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

    returns = None
    has_yielded = False

    async for i in postman.aassign(x):
        if i.kind == AssignationEventKind.YIELD:
            has_yielded = True
            returns = i.returns

        if i.kind == AssignationEventKind.DONE:
            assert has_yielded, "Received DONE without YIELD. This is an error."
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
            assert i.returns is not None, "YIELD event must have returns"
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
) -> tuple[Any]:
    """Call the assignation function"""
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
    """Async generator that yields the results of the assignation"""
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

    async for i in aiterate_raw(
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
            action, i, structure_registry=structure_registry
        )
        if len(returns) == 1:
            yield returns[0]
        else:
            yield returns


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
    """Call the assignation function"""
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
    """Iterate over the results of the assignation"""
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
