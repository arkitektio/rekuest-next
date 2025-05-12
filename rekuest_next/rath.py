"""The base graphql client for rekuest next"""

from types import TracebackType
from typing import Optional
from pydantic import Field
from rath import rath
import contextvars
from rath.links.auth import AuthTokenLink

from rath.links.compose import TypedComposedLink
from rath.links.dictinglink import DictingLink
from rath.links.shrink import ShrinkingLink
from rath.links.split import SplitLink
from rath.links.retry import RetryLink

current_rekuest_next_rath: contextvars.ContextVar[Optional["RekuestNextRath"]] = (
    contextvars.ContextVar("current_rekuest_next_rath", default=None)
)


class RekuestNextLinkComposition(TypedComposedLink):
    """A composition of links for Rekuest Next."""

    shrink: ShrinkingLink = Field(
        default_factory=ShrinkingLink,
        description="Shrinks potential structures in the request.",
    )
    dicting: DictingLink = Field(
        default_factory=DictingLink, description="Dicts the request and response."
    )
    auth: AuthTokenLink
    retry: RetryLink = Field(
        default_factory=RetryLink, description="Retries the request if it fails."
    )
    split: SplitLink


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
