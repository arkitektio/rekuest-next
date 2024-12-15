from typing import Optional
from fakts_next import Fakts
from herre_next import Herre
from rekuest_next.agents.transport.websocket import WebsocketAgentTransport
from pydantic import Field, BaseModel

from typing import Any, Awaitable, Callable, Dict



class WebsocketAgentTransportConfig(BaseModel):
    endpoint_url: str
    instance_id: str = "default"


async def fake_token_loader(*args, **kwargs):
    raise NotImplementedError("You did not set a token loader")


class ArkitektWebsocketAgentTransport(WebsocketAgentTransport):
    endpoint_url: Optional[str]
    instance_id: Optional[str]
    token_loader: Optional[Callable[[], Awaitable[str]]] = Field(
        exclude=True, default=fake_token_loader
    )
    fakts: Fakts
    herre: Herre
    fakts_group: str
    _old_fakt: Dict[str, Any] = {}

    def configure(self, fakt: WebsocketAgentTransportConfig) -> None:
        self.endpoint_url = fakt.endpoint_url
        self.token_loader = self.herre.aget_token

    async def aconnect(self, *args, **kwargs):
        if self.fakts.has_changed(self._old_fakt, self.fakts_group):
            self._old_fakt = await self.fakts.aget(self.fakts_group)
            self.configure(WebsocketAgentTransportConfig(**self._old_fakt))

        return await super().aconnect(*args, **kwargs)
