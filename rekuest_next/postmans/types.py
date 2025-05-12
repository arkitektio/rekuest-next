"""Postman types"""

from types import TracebackType
from typing import AsyncGenerator, Protocol, runtime_checkable
from rekuest_next.api.schema import (
    AssignInput,
    AssignationEvent,
)


@runtime_checkable
class Postman(Protocol):
    """Postman

    Postmans allow to wrap the async logic of the rekuest-server and

    """

    connected: bool
    instance_id: str

    def aassign(self, assign: AssignInput) -> AsyncGenerator[AssignationEvent, None]:
        """Assign"""
        ...

    async def __aenter__(self) -> "Postman":
        """Enter"""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit"""
        pass
