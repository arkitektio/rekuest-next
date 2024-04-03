from pydantic import Field
from rath import rath
import contextvars
from rath.links.auth import AuthTokenLink

from rath.links.compose import TypedComposedLink
from rath.links.dictinglink import DictingLink
from rath.links.shrink import ShrinkingLink
from rath.links.split import SplitLink
from rath.links.retry import RetryLink

current_rekuest_next_rath = contextvars.ContextVar(
    "current_rekuest_next_rath", default=None
)


class RekuestNextLinkComposition(TypedComposedLink):
    shrink: ShrinkingLink = Field(default_factory=ShrinkingLink)
    dicting: DictingLink = Field(default_factory=DictingLink)
    auth: AuthTokenLink
    retry: RetryLink = Field(default_factory=RetryLink)
    split: SplitLink

    def _repr_html_inline_(self):
        return f"<table><tr><td>auth</td><td>{self.auth.maximum_refresh_attempts}</td></tr></table>"


class RekuestNextRath(rath.Rath):
    link: RekuestNextLinkComposition = Field(default_factory=RekuestNextLinkComposition)

    async def __aenter__(self):
        await super().__aenter__()
        current_rekuest_next_rath.set(self)
        return self

    def _repr_html_inline_(self):
        return f"<table><tr><td>link</td><td>{self.link._repr_html_inline_()}</td></tr></table>"

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await super().__aexit__(exc_type, exc_val, exc_tb)
        current_rekuest_next_rath.set(None)
