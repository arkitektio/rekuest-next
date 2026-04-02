from koil import unkoil

import aiohttp
from pathlib import Path
from rekuest_next.datalayer import DataLayer, current_rekuest_datalayer


def _ensure_parent_directory(file_name: str) -> None:
    parent = Path(file_name).expanduser().resolve().parent
    parent.mkdir(parents=True, exist_ok=True)


async def adownload_presigned_file(
    presigned_url: str,
    file_name: str,
    datalayer: DataLayer | None = None,
):
    datalayer = datalayer or current_rekuest_datalayer.get()
    if not datalayer:
        raise ValueError("Datalayer is not set")

    endpoint_url = await datalayer.get_endpoint_url()
    _ensure_parent_directory(file_name)

    async with aiohttp.ClientSession() as session:
        async with session.get(endpoint_url + presigned_url) as response:
            response.raise_for_status()
            with open(file_name, "wb") as file:
                while True:
                    chunk = await response.content.read(1024)
                    if not chunk:
                        break
                    file.write(chunk)

    return file_name


def download_presigned_file(
    presigned_url: str, file_name: str, datalayer: DataLayer | None = None
):
    return unkoil(
        adownload_presigned_file,
        presigned_url,
        file_name=file_name,
        datalayer=datalayer,
    )
