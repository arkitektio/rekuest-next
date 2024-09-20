from typing import List, Union, Any, AsyncGenerator

from pydantic import Field

from rekuest_next.api.schema import (
    AssignationFragment,
    BindsInput,
    AssignInput,
    CancelInput,
    InterruptInput,
    ReserveInput,
    UnreserveInput,
    ReservationFragment,
    AssignationEventFragment,
)
from koil.composition import KoiledModel
import asyncio


class BasePostman(KoiledModel):
    """Postman


    Postmans are the schedulers of the arkitekt platform, they are taking care
    of the communication between your app and the arkitekt-server. And
    provide abstractions to map the asynchornous message-based nature of the arkitekt-server to
    the (a)sync nature of your app. It maps assignations to functions or generators
    depending on the definition, to mimic an actor-like behaviour.

    """

    connected: bool = Field(default=False)
    instance_id: str

    async def aassign(
        self, input: AssignInput
    ) -> AsyncGenerator[AssignationEventFragment, None]:
        """Idea"""
        yield

    async def areserve(self, input: ReserveInput) -> ReservationFragment: ...

    async def aunreserve(self, input: UnreserveInput) -> ReservationFragment: ...
