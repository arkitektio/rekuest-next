"""A module to manage synchronization between multiple actors."""

import asyncio
from typing import Optional, Self

from rekuest_next.agents.lock import TaskLock


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


class SyncKeyLock:
    """A lock with tracking of the current holder (assignation ID)."""

    def __init__(self, key: str) -> None:
        """Initialize the SyncKeyLock.

        Args:
            key: The sync key name.
        """
        self.key = key
        self.lock = asyncio.Lock()
        self.current_holder: Optional[str] = None
        self.holder_interface: Optional[str] = None

    async def acquire(self, assignation_id: str, interface: str) -> Self:
        """Acquire the lock and set the current holder.

        Args:
            assignation_id: The ID of the assignation acquiring the lock.
            interface: The interface name of the holder.

        Returns:
            SyncKeyLock: The lock instance.
        """
        await self.lock.acquire()
        self.current_holder = assignation_id
        self.holder_interface = interface
        return self

    async def release(self) -> None:
        """Release the lock and clear the current holder."""
        self.current_holder = None
        self.holder_interface = None
        if self.lock.locked():
            self.lock.release()

    def is_locked(self) -> bool:
        """Check if the lock is currently held."""
        return self.lock.locked()

    def get_status(self) -> dict:
        """Get the current status of the lock.

        Returns:
            A dictionary with lock status information.
        """
        return {
            "key": self.key,
            "locked": self.is_locked(),
            "holder": self.current_holder,
            "interface": self.holder_interface,
        }


class SyncKeyManager:
    """Manager for sync key locks across all implementations.

    This manager creates and manages asyncio locks for sync keys defined
    in implementations. It tracks which assignation currently holds each lock.
    """

    def __init__(self) -> None:
        """Initialize the SyncKeyManager."""
        self._locks: dict[str, SyncKeyLock] = {}
        self._key_to_interfaces: dict[str, set[str]] = {}

    def register_sync_keys(self, interface: str, sync_keys: tuple[str, ...]) -> None:
        """Register sync keys for an interface.

        Args:
            interface: The interface name.
            sync_keys: The sync keys required by this interface.
        """
        for key in sync_keys:
            if key not in self._locks:
                self._locks[key] = SyncKeyLock(key)
            if key not in self._key_to_interfaces:
                self._key_to_interfaces[key] = set()
            self._key_to_interfaces[key].add(interface)

    def get_lock(self, key: str) -> Optional[SyncKeyLock]:
        """Get a specific lock by key.

        Args:
            key: The sync key name.

        Returns:
            The SyncKeyLock or None if not found.
        """
        return self._locks.get(key)

    def get_locks_for_keys(self, keys: tuple[str, ...]) -> list[SyncKeyLock]:
        """Get locks for a list of keys.

        Args:
            keys: The sync key names.

        Returns:
            A list of SyncKeyLock instances.
        """
        return [self._locks[key] for key in keys if key in self._locks]

    def get_all_keys(self) -> list[str]:
        """Get all registered sync keys.

        Returns:
            A list of all sync key names.
        """
        return list(self._locks.keys())

    def get_all_status(self) -> list[dict]:
        """Get the status of all locks.

        Returns:
            A list of status dictionaries for all locks.
        """
        return [lock.get_status() for lock in self._locks.values()]

    def get_interfaces_for_key(self, key: str) -> set[str]:
        """Get all interfaces that use a given sync key.

        Args:
            key: The sync key name.

        Returns:
            A set of interface names.
        """
        return self._key_to_interfaces.get(key, set())


class SyncKeyGroup(BaseGroup):
    """A sync group that acquires multiple sync key locks.

    This class is used by actors to acquire all required sync key locks
    before executing an assignment.
    """

    def __init__(
        self,
        locks: list[TaskLock],
        assignation_id: str,
        interface: str,
        name: str = "SyncKeyGroup",
    ) -> None:
        """Initialize the SyncKeyGroup.

        Args:
            locks: The list of TaskLock instances to acquire.
            assignation_id: The ID of the assignation.
            interface: The interface name.
            name: The name of the group.
        """
        self.name = name
        self.locks = locks
        self.assignation_id = assignation_id
        self.interface = interface
        self._acquired_locks: list[TaskLock] = []

    async def acquire(self) -> Self:
        """Acquire all locks in order.

        Locks are acquired in a consistent order (by key name) to prevent deadlocks.

        Returns:
            SyncKeyGroup: The SyncKeyGroup instance.
        """
        # Sort locks by key name to ensure consistent ordering and prevent deadlocks
        sorted_locks = sorted(self.locks, key=lambda x: x.lock_schema.key)
        for lock in sorted_locks:
            await lock.acquire(self.assignation_id)
            self._acquired_locks.append(lock)
        return self

    async def wait(self) -> None:
        """Wait is not applicable for SyncKeyGroup."""
        pass

    async def release(self) -> None:
        """Release all acquired locks in reverse order."""
        for lock in reversed(self._acquired_locks):
            await lock.release()
        self._acquired_locks.clear()
