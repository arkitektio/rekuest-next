import asyncio
import uuid
from typing import Any, AsyncGenerator, List, Optional, Union

from koil import unkoil, unkoil_gen
from koil.composition.base import KoiledModel

from rekuest_next.actors.vars import get_current_assignation_helper
from rekuest_next.api.schema import (
    AssignationEventKind,
    AssignInput,
    HookInput,
    NodeFragment,
    ReservationFragment,
    ReserveInput,
    TemplateFragment,
    UnreserveInput,
    afind,
    areserve,
    aunreserve,
)
from rekuest_next.postmans.base import BasePostman
from rekuest_next.postmans.vars import get_current_postman
from rekuest_next.structures.registry import get_current_structure_registry
from rekuest_next.structures.serialization.postman import aexpand_returns, ashrink_args


def useUser() -> str:
    """Use the current User

    Returns:
        User: The current User
    """
    helper = get_current_assignation_helper()
    return helper.assignation.user


async def acall(
    *args,
    node: Optional[NodeFragment] = None,
    template: Optional[TemplateFragment] = None,
    reservation: Optional[ReservationFragment] = None,
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
    *args,
    node: Optional[NodeFragment] = None,
    template: Optional[TemplateFragment] = None,
    reservation: Optional[ReservationFragment] = None,
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
    *args,
    node: Optional[NodeFragment] = None,
    template: Optional[TemplateFragment] = None,
    reservation: Optional[ReservationFragment] = None,
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
    *args,
    node: Optional[NodeFragment] = None,
    template: Optional[TemplateFragment] = None,
    reservation: Optional[ReservationFragment] = None,
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


class ReservationContext(KoiledModel):
    node: NodeFragment
    constants: Optional[dict[str, Any]] = (None,)
    reference: Optional[str] = (None,)
    hooks: Optional[List[HookInput]] = (None,)
    cached: bool = (False,)
    parent: bool = (None,)
    log: bool = (False,)
    assignation_id: Optional[str] = (None,)

    async def __aenter__(self) -> "ReservationContext":

        self._reservation = areserve(
            ReserveInput(
                node=self.node,
                assignationId=self.assignation_id,
            )
        )

        return self

    async def acall(self, *args, **kwargs):
        assert self._reservation, "Not in reservation context"
        return await acall(
            node=self.node, reservation=self._reservation, *args, **kwargs
        )

    def call(self, *args, **kwargs):
        return unkoil(self.acall, *args, **kwargs)

    async def aiterate(self, *args, **kwargs):
        assert self._reservation, "Not in reservation context"
        async for i in aiterate(
            node=self.node, reservation=self._reservation, *args, **kwargs
        ):
            yield i

    def iterate(self, *args, **kwargs):
        return unkoil_gen(self.aiterate, *args, **kwargs)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        from rekuest_next.api.schema import ReserveInput, UnreserveInput, aunreserve

        if self._reservation:
            await aunreserve(UnreserveInput(reservation=self._reservation))

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.reservation.unreserve()

    def __enter__(self) -> "ReservationContext":
        return super().__enter__()


def reserved(
    node: NodeFragment,
    reference: Optional[str] = None,
    hooks: Optional[List[HookInput]] = None,
    cached: bool = False,
    parent: bool = None,
    log: bool = False,
    constants: Optional[dict[str, Any]] = None,
    assignation_id: Optional[str] = None,
) -> ReservationContext:

    assignation_id = assignation_id or get_current_assignation_helper().assignation

    return ReservationContext(
        node,
        reference=reference,
        hooks=hooks,
        cached=cached,
        parent=parent,
        log=log,
        constants=constants,
        assignation_id=assignation_id,
    )
