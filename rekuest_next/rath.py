"""The base graphql client for rekuest next"""

from types import TracebackType
from typing import Optional
from rath import rath
import contextvars

current_rekuest_next_rath: contextvars.ContextVar[Optional["RekuestNextRath"]] = (
    contextvars.ContextVar("current_rekuest_next_rath", default=None)
)


class RekuestNextRath(rath.Rath):
    """A Rath client for Rekuest Next.

    This class is a wrapper around the Rath client and provides
    a default composition of links for Rekuest Next, that allows
    for authentication, retrying, and shrinking of requests.

    """

    async def __aenter__(self) -> "RekuestNextRath":
        """Set the current Rekuest Next Rath client in the context variable."""
        await super().__aenter__()
        current_rekuest_next_rath.set(self)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Unset the current Rekuest Next Rath client in the context variable."""
        await super().__aexit__(exc_type, exc_val, exc_tb)
        current_rekuest_next_rath.set(None)
