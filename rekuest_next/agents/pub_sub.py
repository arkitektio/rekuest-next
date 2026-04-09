import asyncio


from typing import Generic, Set, TypeVar

T = TypeVar("T")


class PubSub(Generic[T]):
    def __init__(self):
        # We store subscribers in a set of Queues
        self.subscribers: Set[asyncio.Queue[T]] = set()

    async def subscribe(self) -> asyncio.Queue[T]:
        """Creates a new queue for a subscriber and adds it to the set."""
        queue = asyncio.Queue[T]()
        self.subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[T]):
        """Removes the queue from the subscriber set."""
        self.subscribers.discard(queue)

    async def publish(self, message: T):
        """Sends a message to all active subscriber queues."""
        if not self.subscribers:
            return

        # We use asyncio.gather to ensure all queues receive the message concurrently
        # Note: In a real-world high-load scenario, you'd handle full queues here.
        await asyncio.gather(*[queue.put(message) for queue in self.subscribers])
