"""The AssignmentHelper is a helper class that is used to manage the assignment"""

from typing import Any, Optional, Self
from pydantic import BaseModel, ConfigDict
from rekuest_next.api.schema import LogLevel
from koil import unkoil
from rekuest_next import messages
from rekuest_next.actors.vars import (
    current_task_helper,
)
from rekuest_next.actors.types import Actor, AssignmentHook
from rekuest_next.postmans.vars import current_postman


class AssignmentHelper(BaseModel):
    """Helper class to manage an assignment during its lifetime.

    Can be used to send logs, progress and to inspect for breakpoints.
    """

    assignment: messages.Assign
    actor: Actor
    model_config = ConfigDict(arbitrary_types_allowed=True)
    _token = None
    _postman_token = None

    async def alog(
        self: Self, level: LogLevel | messages.LogLevelLiteral, message: str
    ) -> None:
        """Send a log message to the actor.

        Args:
            level (LogLevel): The log level.
            message (str): The log message.
        """
        await self.actor.asend(
            message=messages.Log(
                task=self.assignment.task,
                level=level.value if isinstance(level, LogLevel) else level,
                message=message,
            )
        )

    def install_hook(self, hook: "AssignmentHook") -> None:
        """Install an assignment hook for the current task.

        Args:
            hook (AssignmentHook): The hook to install.
        """
        self.actor.install_assignment_hook(self.assignment.task, hook)

    async def aprogress(self, progress: int, message: Optional[str] = None) -> None:
        """Send a progress message to the actor.

        Args:
            progress (int): The progress percentage.
            message (Optional[str]): The progress message.
        """
        if progress < 0 or progress > 100:
            raise ValueError("Progress must be between 0 and 100")

        await self.actor.asend(
            message=messages.Progress(
                task=self.assignment.task,
                progress=progress,
                message=message,
            )
        )

    async def abreakpoint(self) -> bool:
        """Check if the actor needs to break"""
        return await self.actor.abreak(self.assignment.task)
        # await self.actor.acheck_needs_break()

    def breakpoint(self) -> bool:
        """Check if the actor needs to break

        This is a blocking call, and should be
        only called from a seperath thread (i.e
        from the actor thread
        )

        """
        return unkoil(self.abreakpoint)

    def progress(self, progress: int, message: Optional[str] = None) -> None:
        """Send a progress message to the agent.

        Args:
            progress (int): The progress percentage.
            message (Optional[str]): The progress message.
        """

        return unkoil(self.aprogress, progress, message=message)

    def log(self, level: LogLevel, message: str) -> None:
        """Send a log message to the agent.

        Args:
            level (LogLevel): The log level.
            message (str): The log message.
        """
        return unkoil(self.alog, level, message)

    @property
    def user(self) -> str:
        """Returns the user that caused the task"""
        return self.assignment.user

    @property
    def task(self) -> str:
        """Returns the governing task that cause the chained that lead to this execution"""
        return self.assignment.task

    @property
    def org(self) -> str:
        """Returns the organization that caused the task"""
        return self.assignment.org

    @property
    def action(self) -> str:
        """Returns the node that caused the task"""
        return self.assignment.action

    @property
    def args(self) -> dict[str, Any]:
        """Returns the args that caused the task"""
        return self.assignment.args

    @property
    def token(self) -> str | None:
        """Returns the opaque provenance token of the task, if any.

        The token is forwarded untouched to downstream services; it is None
        when the implementation opted out of provenance (needs_token=False).
        """
        return self.assignment.token

    def __enter__(self) -> Self:
        """Set the current task helper to this instance.
        This is used to send logs and progress messages to the actor.

        Within this context all get_task_helper() calls will return this instance.
        """

        self._token = current_task_helper.set(self)
        # Route actor-internal acall/acall_dependency over the agent socket (instead of the
        # GraphQL postman) for the duration of this task body. Standalone callers outside an
        # actor never enter here, so they keep the app's GraphQL postman.
        self._postman_token = current_postman.set(self.actor.agent.caller_postman)
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Optional[type],
    ) -> None:
        """Exit the context manager

        Args:
            exc_type (Optional[type]): The type of the exception
            exc_val (Optional[Exception]): The exception value
            exc_tb (Optional[type]): The traceback
        """
        if self._postman_token:
            current_postman.reset(self._postman_token)
        if self._token:
            current_task_helper.reset(self._token)

    async def __aenter__(self) -> Self:
        """Set the current task helper to this instance.
        This is used to send logs and progress messages to the actor.
        Within this context all get_task_helper() calls will return this instance.
        """

        return self.__enter__()

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Optional[type],
    ) -> None:
        """Exit the async context manager

        Args:
            exc_type (Optional[type]): The type of the exception
            exc_val (Optional[Exception]): The exception value
            exc_tb (Optional[type]): The traceback
        """
        return self.__exit__(exc_type, exc_val, exc_tb)
