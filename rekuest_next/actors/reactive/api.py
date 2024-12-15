from rekuest_next.actors.vars import (
    get_current_assignation_helper,
)
from rekuest_next.api.schema import LogLevel
from typing import Optional


async def alog(message: str, level: LogLevel = LogLevel.DEBUG) -> None:
    await get_current_assignation_helper().alog(level, message)


def log(message: str, level: LogLevel = LogLevel.DEBUG) -> None:
    if not isinstance(message, str):
        message = str(message)

    get_current_assignation_helper().log(level, message)


def useUser() -> str:
    """Returns the user id of the current assignation"""
    return get_current_assignation_helper().user


def useInstanceID() -> str:
    """Returns the guardian id of the current provision"""
    return get_current_assignation_helper().passport.instance_id


def progress(percentage: int, message: Optional[str] = None) -> None:
    """Progress

    Args:
        percentage (int): Percentage to progress to
    """

    helper = get_current_assignation_helper()
    helper.progress(int(percentage), message=message)


async def aprogress(percentage: int, message: Optional[str] = None) -> None:
    """Progress

    Args:
        percentage (int): Percentage to progress to
    """

    helper = get_current_assignation_helper()
    await helper.aprogress(int(percentage), message=message)
