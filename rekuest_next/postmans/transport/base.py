from typing import (
    List,
    Optional,
    Dict,
    Any,
    Protocol,
    runtime_checkable,
)

from rekuest_next.messages import Assignation, Reservation, Unassignation, Unreservation
from rekuest_next.api.schema import (
    AssignationStatus,
    ReservationStatus,
    ReserveParamsInput,
)


@runtime_checkable
class PostmanTransport(Protocol):
    connected = False

    async def aassign(
        self,
        reservation: str,
        args: List[Any],
        kwargs: Dict[str, Any],
        persist=True,
        log=False,
    ) -> Assignation: ...

    async def aunassign(self, assignation: str) -> Unassignation: ...

    async def areserve(
        self,
        node: str,
        params: ReserveParamsInput = None,
        provision: str = None,
        reference: str = "default",
    ) -> Reservation: ...

    async def aunreserve(
        self,
        reservation: str,
    ) -> Unreservation: ...

    async def alist_assignations(
        self, exclude: Optional[AssignationStatus] = None
    ) -> List[Assignation]: ...

    async def alist_reservations(
        self, exclude: Optional[ReservationStatus] = None
    ) -> List[Reservation]: ...
