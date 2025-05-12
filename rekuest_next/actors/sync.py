"""A module to manage synchronization between multiple actors."""

import asyncio
from typing import Optional, Self


class BaseGroup:
    """A base class for groups of actors."""

    async def acquire(self) -> Self:
        """Acquire the lock.

        This method will block until the lock is acquired.
        Returns:
            BaseGroup: The BaseGroup instance.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    async def wait(self) -> None:
        """Wait for the lock to be released.

        This method will block until the lock is released.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    async def release(self) -> None:
        """Release the lock.

        This method will release the lock if it is held.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    async def __aenter__(self) -> Self:
        """Enter the context manager.

        This method will acquire the lock and return the SyncGroup instance.
        Returns:
            SyncGroup: The SyncGroup instance.
        """
        return await self.acquire()

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Optional[type],
    ) -> None:
        """Exit the context manager.
        This method will release the lock if it is held.

        Args:
            exc_type (Optional[type]): The type of the exception
            exc_val (Optional[Exception]): The exception value
            exc_tb (Optional[type]): The traceback
        """
        await self.release()


class SyncGroup(BaseGroup):
    """A class to manage synchronization between multiple actors.

    This class uses asyncio locks to ensure that only one actor can
    access a shared resource at a time. It provides methods to acquire
    and release the lock, as well as to wait for the lock to be released.

    This shared lock can be part of a group of actors or a state and
    can be used to synchronize access to a shared resource.
    """

    def __init__(self, name: str = "None") -> None:
        """Initialize the SyncGroup.

        Args:
            name (str): The name of the group.
        """
        self.name = name
        self.lock = asyncio.Lock()  # Add this line

    async def acquire(self) -> Self:
        """Acquire the lock.

        This method will block until the lock is acquired.
        Returns:
            SyncGroup: The SyncGroup instance.
        """
        await self.lock.acquire()
        return self

    async def wait(self) -> None:
        """Wait for the lock to be released.

        This method will block until the lock is released.

        """
        if not self.lock.locked():
            await self.lock.acquire()

    async def release(self) -> None:
        """Release the lock.

        This method will release the lock if it is held.
        """
        if self.lock.locked():
            self.lock.release()


class ParallelGroup(BaseGroup):
    """A class to manage synchronization between multiple actors.

    Instead of using a lock, this class allows fully asyncio
    parallel execution of actors. It provides methods to acquire
    """

    def __init__(self, name: str = "None") -> None:
        """Initialize the ParallelGroup.
        Args:
            name (str): The name of the group.
        """
        self.name = name

    async def acquire(self) -> Self:
        """Acquire the lock.
        This method will block until the lock is acquired.
        Returns:
            ParallelGroup: The ParallelGroup instance.
        """
        return self

    async def wait(self) -> None:
        """Wait for the lock to be released.
        This method will block until the lock is released.
        """
        return None

    async def release(self) -> None:
        """Release the lock.

        This method will release the lock if it is held.
        """
        pass
        return None
