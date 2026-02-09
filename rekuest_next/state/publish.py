from typing import Any, Optional, Protocol, runtime_checkable
from contextvars import ContextVar

from attr import dataclass

publish_context: ContextVar[Optional["Publisher"]] = ContextVar(
    "publish_context", default=None
)


@dataclass
class Patch:
    op: str
    path: str
    value: Any = None
    old_value: Any = None

    def __str__(self):
        return f"Patch(op={self.op}, path={self.path}, value={self.value}, old_value={self.old_value})"


@runtime_checkable
class StateHolder(Protocol):
    """Protocol for publisher functions"""

    def publish_patch(self, interface: str, patch: Patch) -> None:
        """Method to publish a change to a specific field of the state

        Args:
            interface: The state interface name (e.g., "StageState")
            patch: The patch containing op, path, value, and old_value
        """
        ...


@runtime_checkable
class Publisher(Protocol):
    """Protocol for publisher context managers"""

    def publish_patch(self, interface: str, patch: Patch) -> None:
        """Method to publish a change to a specific field of the state

        Args:
            interface: The state interface name (e.g., "StageState")
            patch: The patch containing op, path, value, and old_value
        """
        ...


class BasePublisher:
    def __init__(self, state_holder: StateHolder) -> None:
        self.state_holder = state_holder
        self._token = None

    def publish_patch(self, interface: str, patch: Patch) -> None:
        """A function that calls indicated to the state_holder that the state was updated"""
        print(f"Publishing patch for {interface}: {patch}")
        return self.state_holder.publish_patch(interface, patch)

    def __enter__(self) -> "BasePublisher":
        self._token = publish_context.set(self)
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_value: Optional[BaseException],
        traceback: Optional[object],
    ) -> None:
        if self._token is not None:
            publish_context.reset(self._token)
        pass

    async def __aenter__(self) -> "BasePublisher":
        self._token = publish_context.set(self)
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_value: Optional[BaseException],
        traceback: Optional[object],
    ) -> None:
        if self._token is not None:
            publish_context.reset(self._token)
        pass


class DirectPublisher(BasePublisher):
    pass


class BufferedPublisher(BasePublisher):
    async def __aenter__(self) -> "BufferedPublisher":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_value: Optional[BaseException],
        traceback: Optional[object],
    ) -> None:
        pass


class NoopPublisher(BasePublisher):
    def publish_patch(self, interface: str, patch: Patch) -> None:
        pass


def noop_publisher() -> Publisher:
    """A no-op publisher that can be used to suppress publishing during intermediate steps."""

    return NoopPublisher(state_holder=None)  # type: ignore


def direct_publishing(state_holder: StateHolder) -> Publisher:
    """
    When used as a context manager, indicates that state updates should be published directly.

    Args:
        state_holder (StateHolder): The state holder to use for publishing.
    Returns:
        Publisher: A publisher that publishes state updates directly.

    """
    return DirectPublisher(state_holder)


def get_current_publisher() -> Publisher | None:
    """Get the current publisher from the context variable.

    Returns:
        Publisher: The current publisher.
    """
    publisher = publish_context.get()
    return publisher
