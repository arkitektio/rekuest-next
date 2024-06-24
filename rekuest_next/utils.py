from typing import Any, AsyncGenerator
from rekuest_next.actors.vars import get_current_assignation_helper
from rekuest_next.postmans.vars import get_current_postman
from rekuest_next.postmans.base import BasePostman
from rekuest_next.structures.serialization.postman import ashrink_args, aexpand_returns
from rekuest_next.structures.registry import get_current_structure_registry

from rekuest_next.api.schema import (
    NodeFragment,
    AssignInput,
    HookInput,
    afind,
    AssignationEventKind,
)
from koil import unkoil, unkoil_gen
import uuid
import asyncio
from typing import Optional, List, Union


def useUser() -> str:
    """Use the current User

    Returns:
        User: The current User
    """
    helper = get_current_assignation_helper()
    return helper.assignation.user


async def acall(
    node: Union[NodeFragment, str],
    *args,
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    parent: bool = None,
    log: bool = False,
    **kwargs,
) -> tuple[Any]:
    if not isinstance(node, NodeFragment):
        node = await afind(id=node)

    postman: BasePostman = get_current_postman()
    structure_registry = get_current_structure_registry()

    shrinked_args = await ashrink_args(
        node, args, kwargs, structure_registry=structure_registry
    )

    instance_id = postman.instance_id

    try:
        parent = parent or get_current_assignation_helper().assignation
    except:
        print("Not in assignation")
        parent = None

    reference = reference or str(uuid.uuid4())

    value = []
    async for i in postman.aassign(
        AssignInput(
            instanceId=instance_id,
            node=node.id,
            args=shrinked_args,
            reference=reference,
            hooks=hooks or [],
            cached=cached,
            parent=parent,
            log=log,
            isHook=False,
        )
    ):
        print(i)
        if i.kind == AssignationEventKind.YIELD:
            value = i.returns

        if i.kind == AssignationEventKind.DONE:
            return await aexpand_returns(
                node, value, structure_registry=structure_registry
            )


async def aiterate(
    node: Union[NodeFragment, str],
    *args,
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    parent: bool = None,
    log: bool = False,
    **kwargs,
) -> AsyncGenerator[tuple[Any], None]:
    if not isinstance(node, NodeFragment):
        node = await afind(id=node)

    postman: BasePostman = get_current_postman()
    structure_registry = get_current_structure_registry()

    shrinked_args = await ashrink_args(
        node, args, kwargs, structure_registry=structure_registry
    )

    instance_id = postman.instance_id

    try:
        parent = parent or get_current_assignation_helper().assignation
    except:
        print("Not in assignation")
        parent = None

    reference = reference or str(uuid.uuid4())

    async for i in postman.aassign(
        AssignInput(
            instanceId=instance_id,
            node=node.id,
            args=shrinked_args,
            reference=reference,
            hooks=hooks or [],
            cached=cached,
            parent=parent,
            log=log,
            isHook=False,
        )
    ):
        if i.kind == AssignationEventKind.YIELD:
            yield await aexpand_returns(
                node, i.returns, structure_registry=structure_registry
            )

        if i.kind == AssignationEventKind.DONE:
            break


def call(
    node: NodeFragment,
    *args,
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    parent: bool = None,
    log: bool = False,
    **kwargs,
) -> tuple[Any]:
    return unkoil(
        acall,
        node,
        reference=reference,
        hooks=hooks,
        cached=cached,
        parent=parent,
        log=log,
        **kwargs,
    )


def iterate(
    node: NodeFragment,
    *args,
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    parent: bool = None,
    log: bool = False,
    **kwargs,
) -> tuple[Any]:
    return unkoil_gen(
        aiterate,
        node,
        reference=reference,
        hooks=hooks,
        cached=cached,
        parent=parent,
        log=log,
        **kwargs,
    )
