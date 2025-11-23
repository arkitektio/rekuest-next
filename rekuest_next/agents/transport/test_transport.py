"""Test Transport for Agents"""

import asyncio
from typing import AsyncIterator, List
from rekuest_next.agents.transport.base import AgentTransport
from rekuest_next import messages
from pydantic import ConfigDict, Field, PrivateAttr


class TestAgentTransport(AgentTransport):
    """Test Agent Transport

    This transport is used for testing purposes. It allows to specify a list of messages
    that will be sent to the agent and asserts that the agent sends back the expected
    messages.
    """

    input_messages: List[messages.ToAgentMessage] = Field(default_factory=list)
    output_messages: List[messages.FromAgentMessage] = Field(default_factory=list)

    _input_queue: asyncio.Queue[messages.ToAgentMessage] = PrivateAttr(
        default_factory=asyncio.Queue
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def add_input_message(self, message: messages.ToAgentMessage) -> None:
        """Add an input message to the queue"""
        self.input_messages.append(message)
        self._input_queue.put_nowait(message)

    async def aconnect(self, instance_id: str) -> None:
        """Connect to the agent transport"""

        # Preload queue
        for message in self.input_messages:
            self._input_queue.put_nowait(message)

    async def areceive(self) -> AsyncIterator[messages.ToAgentMessage]:
        """Receive messages from the agent transport"""
        while True:
            message = await self._input_queue.get()
            yield message
            self._input_queue.task_done()

    async def asend(self, message: messages.FromAgentMessage) -> None:
        """Send a message to the agent"""
        self.output_messages.append(message)

    async def adisconnect(self) -> None:
        """Disconnect the agent transport"""
        pass

    async def assert_output(
        self, expected_messages: List[messages.FromAgentMessage], timeout: float = 1.0
    ) -> None:
        """Assert that the output messages match the expected messages"""

        # Wait for messages to arrive
        start_time = asyncio.get_event_loop().time()
        while len(self.output_messages) < len(expected_messages):
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise AssertionError(
                    f"Timeout waiting for messages. Expected {len(expected_messages)}, got {len(self.output_messages)}"
                )
            await asyncio.sleep(0.01)

        assert len(self.output_messages) == len(expected_messages)
        for i, message in enumerate(expected_messages):
            assert self.output_messages[i] == message
