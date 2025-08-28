"""This module contains the Context API for the actors."""

from rekuest_next.actors.vars import (
    get_current_assignation_helper,
)
from rekuest_next.api.schema import LogLevel
from typing import Optional
from rekuest_next import messages
from rekuest_next.protocols import AnyState
from koil import unkoil


async def apublish(state: AnyState) -> None:
    """Publish a state

    This function is used to publish a state to the actor.

    Args:
        state (AnyState): The state to publish.
    """
    await get_current_assignation_helper().apublish_state(state)


def publish(state: AnyState) -> None:
    """Publish a state

    This function is used to publish a state to the actor.

    Args:
        state (AnyState): The state to publish.
    """
    return unkoil(apublish, state)


async def alog(message: str, level: LogLevel = LogLevel.DEBUG) -> None:
    """Send a log message

    Args:
        message (str): The log message.
        level (LogLevel): The log level.
    """
    try:
        await get_current_assignation_helper().alog(level, message)
    except Exception:  # pylint: disable=broad-except
        # We don't want logging to fail the actor
        print(f"[{level}] {message}")
        pass


def log(message: str, level: LogLevel = LogLevel.DEBUG) -> None:
    """Send a log message

    Args:
        message (str): The log message.
        level (LogLevel): The log level.
    """

    if not isinstance(message, str):  # type: ignore[assignment]
        message = str(message)

    try:
        get_current_assignation_helper().log(level, message)
    except Exception:  # pylint: disable=broad-except
        # We don't want logging to fail the actor
        print(f"[{level}] {message}")
        pass


def useUser() -> str:
    """Returns the user id of the current assignation"""
    return get_current_assignation_helper().user


def useAssign() -> messages.Assign:
    """Returns the assignation id of the current provision"""
    return get_current_assignation_helper().assignment


def useInstanceID() -> str:
    """Returns the guardian id of the current provision"""
    return get_current_assignation_helper().actor.agent.instance_id


def progress(percentage: int, message: Optional[str] = None) -> None:
    """Send Progress

    This function is used to send progress updates to the actor.

    Args:
        percentage (int): Percentage to progress to
        message (Optional[str]): Message to send with the progress

    Raises:
        ValueError: If the percentage is not between 0 and 100
    """

    helper = get_current_assignation_helper()
    helper.progress(int(percentage), message=message)


async def aprogress(percentage: int, message: Optional[str] = None) -> None:
    """Send Progress

    This function is used to send progress updates to the actor.

    Args:
        percentage (int): Percentage to progress to
        message (Optional[str]): Message to send with the progress

    Raises:
        ValueError: If the percentage is not between 0 and 100
    """
    helper = get_current_assignation_helper()
    await helper.aprogress(int(percentage), message=message)


async def abreakpoint() -> None:
    """Await for a breakpoint

    This function is used to await for a breakpoint in the actor.
    A breakpoint can be caused to be activate by a user through
    the rekuest server.
    """

    helper = get_current_assignation_helper()
    await helper.abreakpoint()


def breakpoint() -> None:
    """Await for a breakpoint

    This function is used to await for a breakpoint in the actor.
    A breakpoint can be caused to be activate by a user through
    the rekuest server.
    """

    helper = get_current_assignation_helper()
    helper.breakpoint()
