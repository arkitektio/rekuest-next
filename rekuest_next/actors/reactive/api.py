from rekuest_next.actors.vars import (
    get_current_assignation_helper,
)
from rekuest_next.api.schema import LogLevel
from typing import Dict, Any, Optional


async def alog(message: str, level: LogLevel = LogLevel.DEBUG) -> None:
    await get_current_assignation_helper().alog(level, message)


def log(message: str, level: LogLevel = LogLevel.DEBUG) -> None:
    get_current_assignation_helper().log(level, message)


def useUser() -> str:
    """Returns the user id of the current assignation"""
    return get_current_assignation_helper().user


def useInstanceID() -> str:
    """Returns the guardian id of the current provision"""
    return get_current_assignation_helper().passport.instance_id


def useContext(value: Optional[str] = None) -> Dict[str, Any]:
    context = get_current_assignation_helper().assignment.context
    if value:
        context = context[value]

    return context


def progress(percentage: int) -> None:
    """Progress

    Args:
        percentage (int): Percentage to progress to
    """

    helper = get_current_assignation_helper()
    helper.progress(percentage)


async def aprogress(percentage: int) -> None:
    """Progress

    Args:
        percentage (int): Percentage to progress to
    """

    helper = get_current_assignation_helper()
    await helper.aprogress(percentage)
