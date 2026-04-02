import asyncio
from rath.links.parsing import ParsingLink
from rath.operation import Operation, opify
from typing import Any, Tuple, Type, Union
from rekuest_next.io.upload import (
    astore_media_file,
)
from pydantic import Field
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import TYPE_CHECKING
from rekuest_next.scalars import MediaLike
from rekuest_next.datalayer import DataLayer

if TYPE_CHECKING:
    from rekuest_next.api.schema import (
        MediaUploadGrant,
    )


async def apply_recursive(
    func, obj, typeguard: Union[Type[Any], Tuple[Type[Any], ...]]
) -> Any:  # type: ignore
    """
    Recursively applies an asynchronous function to elements in a nested structure.

    Args:
        func (callable): The asynchronous function to apply.
        obj (any): The nested structure (dict, list, tuple, etc.) to process.
        typeguard (type): The type of elements to apply the function to.

    Returns:
        any: The nested structure with the function applied to elements of the specified type.
    """
    if isinstance(
        obj, dict
    ):  # If obj is a dictionary, recursively apply to each key-value pair
        return {k: await apply_recursive(func, v, typeguard) for k, v in obj.items()}  # type: ignore
    elif isinstance(obj, list):  # If obj is a list, recursively apply to each element
        return await asyncio.gather(
            *[apply_recursive(func, elem, typeguard) for elem in obj]
        )  # type: ignore
    elif isinstance(
        obj, tuple
    ):  # If obj is a tuple, recursively apply to each element and convert back to tuple
        return tuple(
            await asyncio.gather(
                *[apply_recursive(func, elem, typeguard) for elem in obj]
            )  # type: ignore
        )
    elif isinstance(obj, typeguard):
        return await func(obj)  # type: ignore
    else:  # If obj is not a dict, list, tuple, or matching the typeguard, return it as is
        return obj  # type: ignore


class UploadLink(ParsingLink):
    """Data Layer Upload Link

    This link is used to upload  supported types to a DataLayer.
    It parses queries, mutatoin and subscription arguments and
    uploads the items to the DataLayer, and substitures the
    DataFrame with the S3 path.

    Args:
        ParsingLink (_type_): _description_


    """

    datalayer: DataLayer

    executor: ThreadPoolExecutor = Field(
        default_factory=lambda: ThreadPoolExecutor(max_workers=4), exclude=True
    )
    _executor_session: Any = None

    async def __aenter__(self) -> "UploadLink":
        """Enter the context manager for the UploadLink"""
        self._executor_session = self.executor.__enter__()
        return self

    async def aget_media_upload_credentials(
        self, file: MediaLike, datalayer: DataLayer
    ) -> "MediaUploadGrant":
        from rekuest_next.api.schema import (
            RequestMediaUploadInput,
            RequestMediaUploadMutation,
        )

        if not self.next:
            raise ValueError("No next link found. Please set the next link.")

        operation = opify(
            RequestMediaUploadMutation.Meta.document,
            variables={
                "input": RequestMediaUploadInput(
                    originalFileName=file.file_name,
                ).model_dump(by_alias=True, exclude_unset=True)
            },
        )

        async for result in self.next.aexecute(operation):
            return RequestMediaUploadMutation(**result.data).request_media_upload

        raise ValueError("No result found for mesh upload credentials")

    async def aupload_mediafile(
        self,
        file: MediaLike,
        datalayer: "DataLayer",
    ) -> str:
        """Upload a media file to the DataLayer asynchronously."""
        assert datalayer is not None, "Datalayer must be set"
        endpoint_url = await datalayer.get_endpoint_url()

        credentials = await self.aget_media_upload_credentials(file, endpoint_url)

        return await astore_media_file(
            file,
            credentials,
            datalayer,
        )

    async def aparse(self, operation: Operation) -> Operation:
        """Parse the operation (Async)

        Extracts the DataFrame from the operation and uploads it to the DataLayer.

        Args:
            operation (Operation): The operation to parse

        Returns:
            Operation: _description_
        """

        operation.variables = await apply_recursive(
            partial(self.aupload_mediafile, datalayer=self.datalayer),
            operation.variables,
            (MediaLike),
        )
        return operation

    async def adisconnect(self) -> None:
        """Disconnect the UploadLink"""
        self.executor.__exit__(None, None, None)
