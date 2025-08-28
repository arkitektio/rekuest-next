"""The AssignmentHelper is a helper class that is used to manage the assignment"""

from typing import Any, Optional, Self
from pydantic import BaseModel, ConfigDict
from rekuest_next.api.schema import LogLevel
from koil import unkoil
from rekuest_next import messages
from rekuest_next.actors.vars import (
    current_assignation_helper,
)
from rekuest_next.actors.types import Actor
from rekuest_next.protocols import AnyState
from rath.scalars import ID


class AssignmentHelper(BaseModel):
    """Helper class to manage an assignment during its lifetime.

    Can be used to send logs, progress and to inspect for breakpoints.
    """

    assignment: messages.Assign
    actor: Actor
    model_config = ConfigDict(arbitrary_types_allowed=True)
    _token = None

    async def alog(self: Self, level: LogLevel | messages.LogLevelLiteral, message: str) -> None:
        """Send a log message to the actor.

        Args:
            level (LogLevel): The log level.
            message (str): The log message.
        """
        await self.actor.asend(
            message=messages.LogEvent(
                assignation=self.assignment.assignation,
                level=level.value if isinstance(level, LogLevel) else level,
                message=message,
            )
        )

    def get_dependency(self, reference: str) -> ID:
        """Get a dependency by its reference."""
        try:
            return self.assignment.dependencies[reference]
        except KeyError as e:
            raise KeyError(
                f"Dependency {reference} not found in assignment. Did you declare it?"
            ) from e

    async def aprogress(self, progress: int, message: Optional[str] = None) -> None:
        """Send a progress message to the actor.

        Args:
            progress (int): The progress percentage.
            message (Optional[str]): The progress message.
        """
        if progress < 0 or progress > 100:
            raise ValueError("Progress must be between 0 and 100")

        await self.actor.asend(
            message=messages.ProgressEvent(
                assignation=self.assignment.assignation,
                progress=progress,
                message=message,
            )
        )

    async def apublish_state(self: Self, state: AnyState) -> None:
        """Publish the state of the actor.

        Args:
            state (AnyState): The state to publish.
        """
        await self.actor.apublish_state(state)

    async def abreakpoint(self) -> bool:
        """Check if the actor needs to break"""
        return await self.actor.abreak(self.assignment.assignation)
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
        """Returns the user that caused the assignation"""
        return self.assignment.user

    @property
    def assignation(self) -> str:
        """Returns the governing assignation that cause the chained that lead to this execution"""
        return self.assignment.assignation

    @property
    def org(self) -> str:
        """Returns the organization that caused the assignation"""
        return self.assignment.org

    @property
    def action(self) -> str:
        """Returns the node that caused the assignation"""
        return self.assignment.action

    @property
    def args(self) -> dict[str, Any]:
        """Returns the args that caused the assignation"""
        return self.assignment.args

    def __enter__(self) -> Self:
        """Set the current assignation helper to this instance.
        This is used to send logs and progress messages to the actor.

        Within this context all get_assignation_helper() calls will return this instance.
        """

        self._token = current_assignation_helper.set(self)
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
        if self._token:
            current_assignation_helper.reset(self._token)

    async def __aenter__(self) -> Self:
        """Set the current assignation helper to this instance.
        This is used to send logs and progress messages to the actor.
        Within this context all get_assignation_helper() calls will return this instance.
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
