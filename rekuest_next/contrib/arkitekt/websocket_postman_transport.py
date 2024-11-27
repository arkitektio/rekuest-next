from typing import Any, Awaitable, Callable, Dict, Optional
from pydantic import Field
from rekuest_next.postmans.transport.websocket import WebsocketPostmanTransport
from herre_next import Herre
from fakts_next import Fakts
from pydantic import BaseModel


class WebsocketPostmanTransportConfig(BaseModel):
    endpoint_url: str
    instance_id: str = "default"


class ArkitektWebsocketPostmanTransport(WebsocketPostmanTransport):
    endpoint_url: Optional[str]
    instance_id: Optional[str]
    token_loader: Optional[Callable[[], Awaitable[str]]] = Field(exclude=True)
    fakts: Fakts
    herre: Herre
    fakts_group: str
    _old_fakt: Dict[str, Any] = {}

    def configure(self, fakt: WebsocketPostmanTransportConfig) -> None:
        self.endpoint_url = fakt.endpoint_url
        self.instance_id = fakt.instance_id
        self.token_loader = self.token_loader or self.herre.aget_token

    async def aconnect(self):
        if self.fakts.has_changed(self._old_fakt, self.fakts_group):
            self._old_fakt = await self.fakts.aget(self.fakts_group)
            self.configure(WebsocketPostmanTransportConfig(**self._old_fakt))

        return await super().aconnect()
