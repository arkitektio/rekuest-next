"""Transport for Arkitekt using Websockets."""

from fakts_next import Fakts
from fakts_next.protocols import FaktValue
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
    fakts_group: str  #

    _old_fakt: FaktValue = {}

    async def aconfigure(self) -> None:
        """Configure the WebsocketAgentTransport."""
        alias = await self.fakts.aget_alias(self.fakts_group)
        self.endpoint_url = alias.to_ws_path("agi")
        self.token_loader = self.fakts.aget_token

    async def aconnect(self, instance_id: str):  # noqa: ANN002, ANN003, ANN201
        """Connect the WebsocketAgentTransport."""
        await self.aconfigure()

        return await super().aconnect(instance_id)  # type: ignore[return-value]
