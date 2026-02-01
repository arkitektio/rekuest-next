from contextvars import ContextVar, Token
from typing import Optional

current_locks: ContextVar[set[str]] = ContextVar("current_locks", default=set())


class LockContextManager:
    def __init__(self, lock_names: tuple[str, ...]) -> None:
        self.locks = lock_names
        self.reset_token: Optional[Token[set[str]]] = None

    def __enter__(self) -> None:
        self.reset_token = current_locks.set(set(self.locks))

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_value: Optional[BaseException],
        traceback: Optional[object],
    ) -> None:
        if self.reset_token is not None:
            current_locks.reset(self.reset_token)


def acquired_locks(*lock_names: str) -> LockContextManager:
    """Context manager to indicate which locks are held"""
    return LockContextManager(lock_names)


def get_acquired_locks() -> set[str]:
    """Get the currently acquired locks"""
    return current_locks.get()
