from rekuest_next.agents.hooks.startup import startup_context
from contextvars import Token
from typing import Optional


class StartupContextManager:
    """Context manager to indicate we are in the startup context"""

    def __init__(self) -> None:
        """Initialize the startup context manager"""
        self._token: Optional[Token[bool]] = None

    def __enter__(self) -> None:
        """Enter the startup context"""
        self._token = startup_context.set(True)

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_value: Optional[BaseException],
        traceback: Optional[object],
    ) -> None:
        """Exit the startup context"""
        if self._token is not None:
            startup_context.reset(self._token)

    async def __aenter__(self) -> None:
        """Enter the startup context"""
        self._token = startup_context.set(True)

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_value: Optional[BaseException],
        traceback: Optional[object],
    ) -> None:
        """Exit the startup context"""
        if self._token is not None:
            startup_context.reset(self._token)


def starting_up() -> StartupContextManager:
    """Check if we are in the startup context"""
    return StartupContextManager()
