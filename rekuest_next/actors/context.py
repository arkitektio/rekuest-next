"""This module contains the Context API for the actors."""

from rekuest_next.actors.errors import NotWithinATaskError
from rekuest_next.actors.types import AssignmentHook
from rekuest_next.actors.vars import (
    get_current_task_helper,
)

from rekuest_next.api.schema import LogLevel
from typing import Optional
from rekuest_next import messages
import logging

logger = logging.getLogger(__name__)


def cast_log_level(level: LogLevel) -> int:
    """Convert a LogLevel to a logging level

    Args:
        level (LogLevel): The log level to convert

    Returns:
        int: The logging level
    """
    if level == LogLevel.DEBUG:
        return logging.DEBUG
    elif level == LogLevel.INFO:
        return logging.INFO
    elif level == LogLevel.WARN:
        return logging.WARNING
    elif level == LogLevel.ERROR:
        return logging.ERROR
    elif level == LogLevel.CRITICAL:
        return logging.CRITICAL
    else:
        raise ValueError(f"Invalid log level: {level}")


def install_hook(hook: "AssignmentHook") -> None:
    """Attach an assignment hook to the current running task.

    Hooks installed here are only attached to the current task helper.
    If the function is called outside a task, the hook is ignored and a
    warning is logged instead of raising.

    Args:
        hook: Hook implementation to register on the current task.

    Examples:
        Install a hook while handling an action::

            def run() -> None:
                install_hook(my_hook)
    """
    try:
        helper = get_current_task_helper()
        helper.install_hook(hook)
    except NotWithinATaskError:
        logger.warning(
            "You installed an assignment hook outside of a task. This hook will not be called."
        )


async def alog(message: str, level: LogLevel = LogLevel.DEBUG) -> None:
    """Send an asynchronous log message for the current task.

    When called inside a task, the message is forwarded to the backend
    through the current task helper. Outside a task, the message
    falls back to the local Python logger.

    Args:
        message: Message to emit.
        level: Backend log level to associate with the message.

    Examples:
        Log from an async action implementation::

            await alog("starting acquisition", level=LogLevel.INFO)
    """
    try:
        await get_current_task_helper().alog(level, message)
    except Exception:  # pylint: disable=broad-except
        logger.debug(
            "You attempted to log a message outside of a task. This message will not be sent to the rekuest server."
        )
        logger.log(cast_log_level(level), f"[{level}] {message}")
        pass


def log(message: str, level: LogLevel = LogLevel.DEBUG) -> None:
    """Send a synchronous log message for the current task.

    The helper coerces non-string values to strings before forwarding them to
    the current task helper. Outside a task, the message is
    emitted through the local Python logger instead.

    Args:
        message: Message to emit.
        level: Backend log level to associate with the message.

    Examples:
        Report progress from a synchronous action::

            log("processing image", level=LogLevel.INFO)
    """

    if not isinstance(message, str):  # type: ignore[assignment]
        message = str(message)

    try:
        get_current_task_helper().log(level, message)
    except Exception:  # pylint: disable=broad-except
        logger.debug(
            "You attempted to log a message outside of a task. This message will not be sent to the rekuest server."
        )
        logger.log(cast_log_level(level), f"[{level}] {message}")
        pass


def useAssign() -> messages.Assign:
    """Returns the task id of the current provision"""
    return get_current_task_helper().assignment


def progress(percentage: int, message: Optional[str] = None) -> None:
    """Publish a synchronous progress update for the current task.

    The update is forwarded to the task helper when one is active. When
    called outside a task, the update is ignored and a warning is
    logged.

    Args:
        percentage: Progress percentage to publish.
        message: Optional human-readable progress message.

    Examples:
        Send a mid-run progress update::

            progress(50, "halfway done")
    """
    try:
        helper = get_current_task_helper()
        helper.progress(int(percentage), message=message)
    except NotWithinATaskError:
        logger.warning(
            "You attempted to send progress outside of a task. This progress update will not be sent to the rekuest server."
        )
        pass


async def aprogress(percentage: int, message: Optional[str] = None) -> None:
    """Publish an asynchronous progress update for the current task.

    This is the async counterpart to :func:`progress`. Outside a task,
    the update is ignored and only a warning is logged.

    Args:
        percentage: Progress percentage to publish.
        message: Optional human-readable progress message.

    Examples:
        Await progress reporting from an async action::

            await aprogress(90, "almost finished")
    """
    try:
        helper = get_current_task_helper()
        await helper.aprogress(int(percentage), message=message)
    except NotWithinATaskError:
        logger.warning(
            "You attempted to send progress outside of a task. This progress update will not be sent to the rekuest server."
        )
        pass


async def apausepoint() -> None:
    """Yield control at a cooperative pause point for the current task.

    If the backend requests a pause or breakpoint, the current task
    helper can suspend here. Outside a task, the call becomes a logged
    no-op instead of failing the action.

    Examples:
        Allow a long-running async action to pause between steps::

            await apausepoint()
    """
    try:
        helper = get_current_task_helper()
        await helper.abreakpoint()
    except NotWithinATaskError:  # pylint: disable=broad-except
        # We don't want breakpoints to fail the actor if not supported
        logger.warning(
            "You attempted to await a breakpoint outside of a task. This breakpoint will not be awaited."
        )
        pass


def pausepoint() -> None:
    """Yield control at a synchronous pause point for the current task.

    This is the synchronous counterpart to :func:`apausepoint`. Outside an
    task, the call is ignored with a warning.

    Examples:
        Allow a long-running synchronous action to pause between steps::

            pausepoint()
    """
    try:
        helper = get_current_task_helper()
        helper.breakpoint()
    except NotWithinATaskError:  # pylint: disable=broad-except
        # We don't want breakpoints to fail the actor if not supported
        logger.warning(
            "You attempted to await a breakpoint outside of a task. This breakpoint will not be awaited."
        )
        pass
