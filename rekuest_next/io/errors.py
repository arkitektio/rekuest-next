class IoError(Exception):
    """Base class for IO Errors"""

    pass


class UploadError(IoError):
    """Error while uploading to the DataLayer"""

    pass


class DownloadError(IoError):
    """Error while downloading from the DataLayer"""

    pass


class PermissionsError(UploadError):
    """Errror wrapper for permission errors"""

    pass
