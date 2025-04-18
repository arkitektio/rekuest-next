import asyncio


class SyncGroup:
    """ A class to manage synchronization between multiple actors.
    
    This class uses asyncio locks to ensure that only one actor can
    access a shared resource at a time. It provides methods to acquire
    and release the lock, as well as to wait for the lock to be released.
    
    This shared lock can be part of a group of actors or a state and
    can be used to synchronize access to a shared resource.
    """
    
    
    
    def __init__(self, name="None") -> None:
        self.name = name
        self.lock = asyncio.Lock()  # Add this line

    async def acquire(self):
        await self.lock.acquire()
        return self

    async def wait(self):
        if not self.lock.locked():
            await self.lock.acquire()

    async def release(self):
        if self.lock.locked():
            self.lock.release()

    async def __aenter__(self):  # Fix: make this async
        return await self.acquire()

    async def __aexit__(self, exc_type, exc_val, exc_tb):  # Fix: make this async
        await self.release()


class ParallelGroup:
    """ A class to manage synchronization between multiple actors.
    
    Instead of using a lock, this class allows fully asyncio
    parallel execution of actors. It provides methods to acquire
    """
    
    
    def __init__(self, name="None") -> None:
        self.name = name

    async def acquire(self):
        return self

    async def wait(self):
        return self

    async def release(self):
        pass
        return self

    async def __aenter__(self):
        return await self.acquire()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()
