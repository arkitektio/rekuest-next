from typing import Any, Dict

from fakts_next.fakts import Fakts
from rekuest_next.datalayer import DataLayer
from pydantic import BaseModel


class DataLayerFakt(BaseModel):
    endpoint_url: str


class FaktsDataLayer(DataLayer):
    """A fakts implementation of the datalayer. This will allow you to connect to a datalayer
    that is defined asnychronously in fakts. This is useful for connecting to a datalayer that
    is not known at compile time. Will get the server configuration from fakts and connect to the
    datalayer."""

    fakts_group: str
    fakts: Fakts

    _old_fakt: Dict[str, Any] = {}
    _configured = False

    async def get_endpoint_url(self) -> str:
        """Get the endpoint URL for the datalayer. This will connect to the fakts group and get the
        endpoint URL from the fakts group. If the datalayer is already configured, it will return the
        endpoint URL. If not, it will connect to the fakts group and get the endpoint URL."""
        if self._configured:
            return self.endpoint_url
        else:
            await self.aconnect()
            return self.endpoint_url

    async def aconnect(self) -> None:
        """Connect to the fakts group and get the endpoint URL. This will set the endpoint URL to the
        fakts group alias. If the fakts group is not configured, it will raise an error."""
        alias = await self.fakts.aget_alias(self.fakts_group)
        self.endpoint_url = alias.to_http_path()
        self.host = alias.host
        self.port = alias.port
        self.protocol = "https" if alias.ssl else "http"

        self._configured = True
