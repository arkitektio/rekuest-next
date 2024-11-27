from .protocol import InMessage, OutMessage
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .extension import DelegatingExtension


class ProcessTransport:

    def __init__(self, extension: "DelegatingExtension"):
        self.extension = extension

    async def asend_message(self, message: OutMessage):
        await self.extension.asend_message(message)

    async def aget_next_message(self) -> InMessage:
        return await self.extension.aget_next_message()
