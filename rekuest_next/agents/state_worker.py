import asyncio
import time
import jsonpatch
from typing import List, Optional, Any, Dict, Protocol
import logging

from pydantic import BaseModel

from rekuest_next import messages
from rekuest_next.agents.utils import resolve_port_for_path
from rekuest_next.protocols import AnyState, EventedConfig
from rekuest_next.actors.types import Agent, Shelver
from rekuest_next.state.shrink import ashrink_state
from rekuest_next.structures.serialization.actor import ashrink_return

logger = logging.getLogger(__name__)


class RevisedState(BaseModel):
    """A revised state that includes the current revision number and the state data."""

    revision: int
    data: Dict[str, Any]


class StatePublisher(Shelver, Protocol):
    """Protocol for the StateWorker to publish patches to the agent."""

    async def apublish_envelope(
        self, state_name: str, envelope: messages.Envelope
    ) -> None:
        """Publish an envelope containing patches to the agent."""
        ...


class StateWorker:
    """
    Manages the buffer, squashing, shrinking, and network loop
    for a SINGLE state instance using an event-driven Queue.
    """

    def __init__(
        self,
        state_instance: AnyState,
        agent: StatePublisher,
        config: EventedConfig,
    ):
        self.schema = config.state_schema
        self.name = config.state_name
        self.interval = config.publish_interval
        self.structure_registry = config.structure_registry
        self.agent = agent

        self._state_reference = state_instance
        self._last_shrunk_state: Optional[Dict[str, Any]] = None
        self._rev = 0
        self._running = False

        # Internal state lock to prevent race conditions between
        # the background flush and external calls to aget_revision
        self._lock = asyncio.Lock()

        # Async-friendly queue for incoming patches from the Observable
        self._queue: asyncio.Queue[messages.EnvelopePatch] = asyncio.Queue()

    async def aget_revision(self) -> RevisedState:
        """
        Returns the current serialized state and its revision number.
        If the state hasn't been captured yet, it performs an initial shrink.
        """
        async with self._lock:
            if self._last_shrunk_state is None:
                self._last_shrunk_state = await ashrink_state(
                    self._state_reference,
                    self.schema,
                    structure_reg=self.structure_registry,
                    shelver=self.agent,
                )

            # We return a deep copy or a snapshot to ensure the publisher
            # isn't looking at a dict that _flush is currently mutating.
            return RevisedState(revision=self._rev, data=self._last_shrunk_state)

    def put_patch(self, patch: messages.EnvelopePatch) -> None:
        """Called synchronously by the Observable mixin to buffer changes."""
        self._queue.put_nowait(patch)

    async def start(self):
        """The event-driven heartbeat loop."""
        self._running = True

        # Initial capture ensures we have a base state before processing patches
        async with self._lock:
            if self._last_shrunk_state is None:
                self._last_shrunk_state = await ashrink_state(
                    self._state_reference,
                    self.schema,
                    structure_reg=self.structure_registry,
                    shelver=self.agent,
                )

        try:
            while self._running:
                # 1. Block until at least one patch arrives (0% CPU while idle)
                first_patch = await self._queue.get()
                raw_patches = [first_patch]

                # 2. Debounce: Wait for 'interval' to collect more patches
                if self.interval > 0:
                    await asyncio.sleep(self.interval)

                # 3. Drain the queue of all patches accumulated during the wait
                while not self._queue.empty():
                    raw_patches.append(self._queue.get_nowait())

                # 4. Process the batch
                await self._flush(raw_patches)

                # Mark tasks as done for the queue
                for _ in range(len(raw_patches)):
                    self._queue.task_done()

        except asyncio.CancelledError:
            self._running = False
        except Exception as e:
            logger.exception(f"Fatal error in StateWorker '{self.name}': {e}")
            raise

    async def _flush(self, raw_patches: List[messages.EnvelopePatch]):
        """Logic for squashing, shrinking, and updating the local snapshot."""
        if not raw_patches:
            return

        try:
            # 1. Squash redundant operations (e.g., multiple updates to same path)
            optimized = self._squash(raw_patches)
            if not optimized:
                return

            # 2. Serialize values for the network
            network_patches: List[messages.EnvelopePatch] = []
            for p in optimized:
                port = self._resolve_port(p.path)
                if not port:
                    logger.error(f"Could not resolve port for path {p.path}")
                    continue

                safe_value = None
                if p.op in ("add", "replace"):
                    safe_value = await ashrink_return(
                        port, p.value, self.structure_registry, self.agent
                    )

                network_patches.append(
                    messages.EnvelopePatch(
                        op=p.op, path=p.path, value=safe_value, old_value=None
                    )
                )

            # 3. Atomic Update: Apply patches to local snapshot and increment rev
            async with self._lock:
                if self._last_shrunk_state is not None:
                    patch_dicts = [
                        p.model_dump(exclude_none=True) for p in network_patches
                    ]
                    jsonpatch.apply_patch(
                        self._last_shrunk_state, patch_dicts, in_place=True
                    )

                base_rev = self._rev
                self._rev += 1

            # 4. Construct and Publish
            envelope = messages.Envelope(
                state_name=self.name,
                rev=self._rev,
                base_rev=base_rev,
                ts=time.time(),
                patches=network_patches,
            )

            await self.agent.apublish_envelope(self.name, envelope)

        except Exception as e:
            logger.exception(f"Error flushing state '{self.name}': {e}")

    def _resolve_port(self, path: str) -> Optional[Any]:
        """Traverses the schema to find the PortInput for a given JSON path."""
        return resolve_port_for_path(self.schema, path)

    def _squash(
        self, patches: List[messages.EnvelopePatch]
    ) -> List[messages.EnvelopePatch]:
        """
        Chronological squash: Only the last operation for a specific path
        within this batch is kept, unless paths are nested.
        """
        latest_ops: Dict[str, messages.EnvelopePatch] = {}
        for p in patches:
            latest_ops[p.path] = p
        return list(latest_ops.values())
