import asyncio


class SyncGroup:
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

    def __init__(self, name="None") -> None:
        self.name = name
        self.lock = asyncio.Lock()

    async def acquire(self):
        await self.lock.acquire()
        return self

    async def wait(self):
        if not self.lock.locked():
            await self.lock.acquire()

    async def release(self):
        if self.lock.locked():
            self.lock.release()

    async def __aenter__(self):
        return await self.acquire()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()
