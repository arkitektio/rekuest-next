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
from rekuest_next.actors.context import useAssignation
from rekuest_next.actors.vars import (
    NotWithinAnAssignationError,
)
from rekuest_next.api.schema import (
    AssignationEvent,
    AssignationEventKind,
    AssignInput,
    HookInput,
    Action,
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


def ensure_return_as_list(value: Any) -> list:  # noqa: ANN401
    """Ensure that the value is a list."""
    if not value:
        return []
    if isinstance(value, tuple):
        return value
    return [value]


async def acall_raw(
    kwargs: Dict[str, Any] = None,
    action: Optional[Action] = None,
    implementation: Optional[Implementation] = None,
    parent: Optional[Assign] = None,
    reservation: Optional[Reservation] = None,
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    assign_timeout: Optional[int] = None,
    timeout_is_recoverable: bool = False,
    log: bool = False,
    postman: Optional[Postman] = None,
) -> Any:  # noqa: ANN401
    """Call the assignation function"""
    postman: Postman = postman or get_current_postman()

    try:
        parent = useAssignation()
    except NotWithinAnAssignationError:
        # If we are not within an assignation, we can set the parent to None
        parent = None

    reference = reference or str(uuid.uuid4())

    x = AssignInput(
        instanceId=postman.instance_id,
        action=action,
        implementation=implementation,
        reservation=reservation,  # type: ignore
        args=kwargs,
        reference=reference,
        hooks=hooks or [],
        cached=cached,
        parent=parent,
        log=log,
        isHook=False,
        ephemeral=False,
    )

    returns = None

    async for i in postman.aassign(x):
        if i.kind == AssignationEventKind.YIELD:
            returns = i.returns

        if i.kind == AssignationEventKind.DONE:
            return returns

        if i.kind == AssignationEventKind.CRITICAL:
            raise Exception(i.message)


async def aiterate_raw(
    kwargs: Dict[str, Any] = None,
    action: Optional[Action] = None,
    implementation: Optional[Implementation] = None,
    parent: Optional[Assign] = None,
    reservation: Optional[Reservation] = None,
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    assign_timeout: Optional[int] = None,
    timeout_is_recoverable: bool = False,
    log: bool = False,
    postman: Optional[Postman] = None,
) -> AsyncGenerator[AssignationEvent, None]:
    """Async generator that yields the results of the assignation"""
    postman: Postman = postman or get_current_postman()

    try:
        parent = useAssignation()
    except NotWithinAnAssignationError:
        # If we are not within an assignation, we can set the parent to None
        parent = None

    reference = reference or str(uuid.uuid4())

    x = AssignInput(
        instanceId=postman.instance_id,
        action=action,
        implementation=implementation,
        reservation=reservation,  # type: ignore
        args=kwargs,
        reference=reference,
        hooks=hooks or [],
        cached=cached,
        parent=parent,
        log=log,
        isHook=False,
        ephemeral=False,
    )

    async for i in postman.aassign(x):
        if i.kind == AssignationEventKind.YIELD:
            yield i.returns

        if i.kind == AssignationEventKind.DONE:
            return

        if i.kind == AssignationEventKind.CRITICAL:
            raise Exception(i.message)


async def acall(
    action_implementation_res: Union[Action, Implementation, Reservation] = None,
    *args,  # noqa: ANN002
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    parent: bool = None,
    log: bool = False,
    structure_registry: Optional[StructureRegistry] = None,
    postman: Optional[Postman] = None,
    **kwargs,  # noqa: ANN003
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

    elif isinstance(action_implementation_res, Action):
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
        parent=parent,
        log=log,
        postman=postman,
    )

    return await aexpand_returns(action, returns, structure_registry=structure_registry)


async def aiterate(
    action_implementation_res: Union[Action, Implementation, Reservation] = None,
    *args,  # noqa: ANN002
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    parent: bool = None,
    log: bool = False,
    structure_registry: Optional[StructureRegistry] = None,
    **kwargs,  # noqa: ANN003
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

    elif isinstance(action_implementation_res, Action):
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

    async for i in await aiterate_raw(
        kwargs=shrinked_args,
        action=action,
        implementation=implementation,
        reservation=reservation,
        reference=reference,
        hooks=hooks or [],
        cached=cached,
        parent=parent,
        log=log,
    ):
        yield aexpand_returns(action, i, structure_registry=structure_registry)


def call(
    *args,  # noqa: ANN002
    **kwargs,  # noqa: ANN003
) -> Any:  # noqa: ANN002, ANN003, ANN401
    """Call the assignation function"""
    return unkoil(
        acall,
        *args,
        **kwargs,
    )


def iterate(
    *args,  # noqa: ANN002
    **kwargs,  # noqa: ANN003
) -> Generator[Any, None, None]:
    """Iterate over the results of the assignation"""
    return unkoil_gen(
        aiterate,
        *args,
        **kwargs,
    )


def call_raw(*args, **kwargs) -> Any:  # noqa: ANN002, ANN003, ANN401
    """Call the raw assignation function"""
    return unkoil(acall_raw, *args, **kwargs)
