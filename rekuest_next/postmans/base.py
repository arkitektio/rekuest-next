from typing import AsyncGenerator

from pydantic import Field

from rekuest_next.api.schema import (
    AssignInput,
    ReserveInput,
    UnreserveInput,
    Reservation,
    AssignationEvent,
)
from koil.composition import KoiledModel


class BasePostman(KoiledModel):
    """Postman


    Postmans allow to wrap the async logic of the rekuest-server and

    """

    connected: bool = Field(default=False)
    instance_id: str

    async def aassign(self, input: AssignInput) -> AsyncGenerator[AssignationEvent, None]:
        """Assign"""
        yield

    async def areserve(self, input: ReserveInput) -> Reservation:
        """Idea"""

        ...

    async def aunreserve(self, input: UnreserveInput) -> Reservation: ...
