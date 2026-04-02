"""
This modules provides the datalayer.

Example:

    A simple datalayer that connects to an s3 instance via access_key and secret_key.
    You can define all of the logic within the context manager

    ```python
    from mikro_next imports Datalayer

    dl = Datalayer(access_key="XXXX", secret_key="XXXX", endpoint_url="s3.amazonaws.com")

    with dl:
        print(df.fs.ls())

    ```

    Async Usage:

    ```python
    from mikro_nextdatalayer import Datalayer

    dl = Datalayer(access_key="XXXX", secret_key="XXXX", endpoint_url="s3.amazonaws.com")

    async with dl:
        print(df.fs.ls())

    ```


"""

import contextvars
from types import TracebackType
from typing import Optional

from koil.composition import KoiledModel


current_rekuest_datalayer: contextvars.ContextVar[Optional["DataLayer"]] = (
    contextvars.ContextVar("current_rekuest_datalayer", default=None)
)


class DataLayer(KoiledModel):
    """Implements a S3 DataLayer

    This will be used to upload and download files from S3.

    Make sure to set the access_key and secret_key and enter the context
    manager to connect to S3 (if authentication is required for the S3 instance
    and to ensure that the context is exited when the context manager is exited
    (for future cleanup purposes on other datalayers).

    Attributes:
        fs (s3fs.S3FileSystem): The filesystem object

    """

    endpoint_url: str = ""
    host: str = ""
    port: int | None = None
    protocol: str = "https"

    async def get_endpoint_url(self):
        return self.endpoint_url

    async def __aenter__(self):
        current_rekuest_datalayer.set(self)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        current_rekuest_datalayer.set(None)
