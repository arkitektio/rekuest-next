"""Postman types"""

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

    async def aassign(self, input: AssignInput) -> AsyncGenerator[AssignationEvent, None]:
        """Assign"""
        yield

    async def __aenter__(self) -> "Postman":
        """Enter"""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Exit"""
        pass
