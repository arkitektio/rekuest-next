"""Module for uploading various data types to a DataLayer using asynchronous methods."""

from typing import TYPE_CHECKING

from rekuest_next.scalars import MediaLike
from .errors import PermissionsError, UploadError

from rekuest_next.datalayer import DataLayer


if TYPE_CHECKING:
    from rekuest_next.api.schema import MediaUploadGrant


async def astore_media_file(
    file: MediaLike,
    credentials: "MediaUploadGrant",
    datalayer: "DataLayer",
) -> str:
    """Store a media file using a presigned PUT URL built from datalayer endpoint and credentials."""
    """Store a DataFrame in the DataLayer"""

    from aiobotocore.session import get_session  # type: ignore
    import botocore  # type: ignore

    session = get_session()

    endpoint_url = await datalayer.get_endpoint_url()

    async with session.create_client(  # type: ignore
        "s3",
        region_name="us-west-2",
        endpoint_url=endpoint_url,
        aws_secret_access_key=credentials.secret_key,
        aws_access_key_id=credentials.access_key,
        aws_session_token=credentials.session_token,
    ) as client:
        try:
            print(credentials, file.value)
            await client.put_object(Bucket=credentials.bucket, Key=credentials.key, Body=file.value)  # type: ignore
        except botocore.exceptions.ClientError as e:  # type: ignore
            if e.response["Error"]["Code"] == "InvalidAccessKeyId":  # type: ignore
                return PermissionsError("Access Key is invalid, trying to get new credentials")  # type: ignore

            raise e

    print(credentials)
    return credentials.store

    return credentials.store
