"""Transport for Arkitekt using Websockets."""

from fakts_next import Fakts
from fakts_next.protocols import FaktValue
from herre_next import Herre
from rekuest_next.agents.transport.websocket import WebsocketAgentTransport
from pydantic import BaseModel



class WebsocketAgentTransportConfig(BaseModel):
    """Configuration for the WebsocketAgentTransport."""

    endpoint_url: str
    instance_id: str = "default"


async def fake_token_loader() -> str:  # noqa: ANN002, ANN003
    """Fake token loader for testing purposes."""
    raise NotImplementedError("You did not set a token loader")


class ArkitektWebsocketAgentTransport(WebsocketAgentTransport):
    """WebsocketAgentTransport for Arkitekt.

    Uses fakts and herre to manage the connection.

    """

    fakts: Fakts
    herre: Herre
    fakts_group: str

    _old_fakt: FaktValue = {}

    def configure(self, fakt: WebsocketAgentTransportConfig) -> None:
        """Configure the WebsocketAgentTransport."""
        self.endpoint_url = fakt.endpoint_url
        self.token_loader = self.herre.aget_token

    async def aconnect(self, instance_id: str):  # noqa: ANN002, ANN003, ANN201
        """Connect the WebsocketAgentTransport."""
        if self.fakts.has_changed(self._old_fakt, self.fakts_group):
            self._old_fakt = await self.fakts.aget(self.fakts_group)
            assert isinstance(self._old_fakt, dict), (
                "Fakts group is not a valid FaktValue"
            )
            self.configure(WebsocketAgentTransportConfig(**self._old_fakt))  # type: ignore

        return await super().aconnect(instance_id)  # type: ignore[return-value]
