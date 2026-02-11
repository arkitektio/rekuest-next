"""This module contains the Context API for the actors."""

from rekuest_next.actors.errors import NotWithinAnAssignationError
from rekuest_next.actors.types import AssignmentHook
from rekuest_next.actors.vars import (
    get_current_assignation_helper,
)

from rekuest_next.api.schema import LogLevel
from typing import Optional
from rekuest_next import messages
from rekuest_next.protocols import AnyState
import logging

logger = logging.getLogger(__name__)


def install_hook(hook: "AssignmentHook") -> None:
    """Install an assignment hook for the current assignation.

    Args:
        hook (AssignmentHook): The hook to install.
    """
    try:
        helper = get_current_assignation_helper()
        helper.install_hook(hook)
    except NotWithinAnAssignationError:
        logger.warning(
            "You installed an assignment hook outside of an assignation. This hook will not be called."
        )


async def apublish(state: AnyState) -> None:
    """Publish a state

    This function is used to publish a state to the actor.

    Args:
        state (AnyState): The state to publish.
    """
    from rekuest_next.state.publish import publish_context

    publisher = publish_context.get()
    if publisher is not None:
        print("Currently not implemented")


def publish(state: AnyState) -> None:
    """Publish a state

    This function is used to publish a state to the actor.

    Args:
        state (AnyState): The state to publish.
    """
    from rekuest_next.state.publish import publish_context

    publisher = publish_context.get()
    if publisher is not None:
        print("Currently not implemented")


async def alog(message: str, level: LogLevel = LogLevel.DEBUG) -> None:
    """Send a log message

    Args:
        message (str): The log message.
        level (LogLevel): The log level.
    """
    try:
        await get_current_assignation_helper().alog(level, message)
    except Exception:  # pylint: disable=broad-except
        logger.warning(
            "You attempted to log a message outside of an assignation. This message will not be sent to the rekuest server."
        )
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
        logger.warning(
            "You attempted to log a message outside of an assignation. This message will not be sent to the rekuest server."
        )
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
    try:
        helper = get_current_assignation_helper()
        helper.progress(int(percentage), message=message)
    except NotWithinAnAssignationError:
        logger.warning(
            "You attempted to send progress outside of an assignation. This progress update will not be sent to the rekuest server."
        )
        pass


async def aprogress(percentage: int, message: Optional[str] = None) -> None:
    """Send Progress

    This function is used to send progress updates to the actor.

    Args:
        percentage (int): Percentage to progress to
        message (Optional[str]): Message to send with the progress

    Raises:
        ValueError: If the percentage is not between 0 and 100
    """
    try:
        helper = get_current_assignation_helper()
        await helper.aprogress(int(percentage), message=message)
    except NotWithinAnAssignationError:
        logger.warning(
            "You attempted to send progress outside of an assignation. This progress update will not be sent to the rekuest server."
        )
        pass


async def apausepoint() -> None:
    """Await for a breakpoint

    This function is used to await for a breakpoint in the actor.
    A breakpoint can be caused to be activate by a user through
    the rekuest server.
    """
    try:
        helper = get_current_assignation_helper()
        await helper.abreakpoint()
    except NotWithinAnAssignationError:  # pylint: disable=broad-except
        # We don't want breakpoints to fail the actor if not supported
        logger.warning(
            "You attempted to await a breakpoint outside of an assignation. This breakpoint will not be awaited."
        )
        pass


def pausepoint() -> None:
    """Await for a breakpoint

    This function is used to await for a breakpoint in the actor.
    A breakpoint can be caused to be activate by a user through
    the rekuest server.
    """
    try:
        helper = get_current_assignation_helper()
        helper.breakpoint()
    except NotWithinAnAssignationError:  # pylint: disable=broad-except
        # We don't want breakpoints to fail the actor if not supported
        logger.warning(
            "You attempted to await a breakpoint outside of an assignation. This breakpoint will not be awaited."
        )
        pass
