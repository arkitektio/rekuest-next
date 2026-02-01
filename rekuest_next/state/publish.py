from typing import Callable, Any, Optional, Protocol, runtime_checkable
from contextvars import ContextVar

from koil import unkoil

from rekuest_next.protocols import AnyState

publish_context: ContextVar[Optional["Publisher"]] = ContextVar(
    "publish_context", default=None
)


@runtime_checkable
class StateHolder(Protocol):
    """Protocol for publisher functions"""

    async def apublish(self, state: AnyState) -> None:
        """Asynchronous publish method"""
        ...


@runtime_checkable
class Publisher(Protocol):
    """Protocol for publisher context managers"""

    async def apublish(self, state: AnyState) -> None:
        """Asynchronous publish method"""
        ...

    def publish(self, state: AnyState) -> None:
        """Synchronous publish method"""
        ...


class BasePublisher:
    def __init__(self, state_holder: StateHolder) -> None:
        self.state_holder = state_holder

    async def adirect_publish(self, state: AnyState) -> None:
        """A function that calls indicated to the state_holder that the state was updated"""
        return await self.state_holder.apublish(state)


class DirectPublisher(BasePublisher):
    async def apublish(self, state: AnyState) -> None:
        """A function that calls indicated to the state_holder that the state was updated"""
        return await self.state_holder.apublish(state=state)

    def publish(self, state: AnyState) -> None:
        """A function that calls indicated to the state_holder that the state was updated"""
        return unkoil(self.state_holder.apublish, state)

    async def __aenter__(self) -> "DirectPublisher":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_value: Optional[BaseException],
        traceback: Optional[object],
    ) -> None:
        pass


class BufferedPublisher(BasePublisher):
    async def apublish(self, state: AnyState) -> None:
        """A function that calls indicated to the state_holder that the state was updated"""

        return await self.state_holder.apublish(state)

    def publish(self, state: AnyState) -> None:
        """A function that calls indicated to the state_holder that the state was updated"""
        return unkoil(self.state_holder.apublish, state)

    async def __aenter__(self) -> "BufferedPublisher":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_value: Optional[BaseException],
        traceback: Optional[object],
    ) -> None:
        pass


class NoopPublisher:
    async def apublish(self, state: AnyState) -> None:
        """A no-op publish method"""
        pass

    def publish(self, state: AnyState) -> None:
        """A no-op publish method"""
        pass


def noop_publishing() -> Publisher:
    """
    When used as a context manager, indicates that state updates should be ignored
    (until the context manager exits).

    Returns:
        Publisher: A publisher that ignores state updates.

    """
    return NoopPublisher()


def direct_publishing(state_holder: StateHolder) -> Publisher:
    """
    When used as a context manager, indicates that state updates should be published directly.

    Args:
        state_holder (StateHolder): The state holder to use for publishing.
    Returns:
        Publisher: A publisher that publishes state updates directly.

    """
    return DirectPublisher(state_holder)


def throttled_publishing(state_holder: StateHolder, throttle: int = 10) -> Publisher:
    """
    When used as a context manager, indicates that state updates should be buffered and published
    at most once every `throttle` seconds.

    Args:
        state_holder (StateHolder): The state holder to use for publishing.
        throttle (int): The throttle interval in seconds. Defaults to 10.
    Returns:
        Publisher: A publisher that buffers state updates and publishes them at most once every `throttle` seconds.

    """
    return BufferedPublisher(state_holder)


def get_current_publisher() -> Publisher | None:
    """Get the current publisher from the context variable.

    Returns:
        Publisher: The current publisher.
    """
    publisher = publish_context.get()
    return publisher
