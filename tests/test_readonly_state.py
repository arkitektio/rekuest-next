"""No-Docker checks that a read-only state declaration is actually enforced.

Declaring a state read-only used to be advisory: the agent handed back the same live
object a writer gets, so an actor could write to a state it declared read-only and the
write would publish a patch like any other.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Dict, List

import pytest

from rekuest_next.agents.base import BaseAgent
from rekuest_next.app import AppRegistry
from rekuest_next.state.decorator import state
from rekuest_next.state.observable import make_evented
from rekuest_next.state.publish import direct_publishing
from rekuest_next.state.readonly import ReadOnlyStateError, read_only_view

from .memory_transport import MemoryAgentTransport


@state
@dataclass
class Board:
    """A state with a scalar and both container kinds."""

    count: int = 0
    items: List[int] = field(default_factory=list)
    meta: Dict[str, int] = field(default_factory=dict)


def _evented_board() -> Board:
    """A Board wired up the way the agent holds one at runtime."""
    return make_evented(Board(), getattr(Board, "__rekuest_state_config__"))


class _RecordingPublisher:
    def __init__(self) -> None:
        self.patches: List[str] = []

    def publish_patch(self, interface: str, patch: object, task_id: str | None = None) -> None:
        self.patches.append(interface)


def test_view_is_still_the_state_type() -> None:
    """User functions are annotated with the state class, so isinstance must hold."""
    board = _evented_board()
    assert isinstance(read_only_view(board, "Board"), Board)


def test_view_reads_are_live_not_a_snapshot() -> None:
    """A reader must see what a writer changed, or the view would be useless."""
    board = _evented_board()
    view = read_only_view(board, "Board")

    board.count = 7
    assert view.count == 7


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda v: setattr(v, "count", 1), id="attribute-write"),
        pytest.param(lambda v: delattr(v, "count"), id="attribute-delete"),
        pytest.param(lambda v: v.items.append(1), id="list-append"),
        pytest.param(lambda v: v.items.insert(0, 1), id="list-insert"),
        pytest.param(lambda v: v.items.__setitem__(0, 1), id="list-setitem"),
        pytest.param(lambda v: v.meta.update({"a": 1}), id="dict-update"),
        pytest.param(lambda v: v.meta.__setitem__("a", 1), id="dict-setitem"),
        pytest.param(lambda v: v.meta.pop("a", None), id="dict-pop"),
    ],
)
def test_every_mutation_path_is_refused(mutate) -> None:
    """Attribute writes and container mutation alike."""
    view = read_only_view(_evented_board(), "Board")
    with pytest.raises(ReadOnlyStateError):
        mutate(view)


def test_refusing_a_write_publishes_nothing() -> None:
    """The point of the enforcement: a refused write must not reach the backend."""
    board = _evented_board()
    view = read_only_view(board, "Board")
    publisher = _RecordingPublisher()

    with direct_publishing(publisher):
        with pytest.raises(ReadOnlyStateError):
            view.count = 3
        with pytest.raises(ReadOnlyStateError):
            view.items.append(1)

    assert publisher.patches == [], "a refused write must not publish a patch"
    assert board.count == 0 and list(board.items) == [], "the state must be untouched"


def test_the_writeable_handle_still_publishes() -> None:
    """Enforcement must not disturb the writer's path."""
    board = _evented_board()
    publisher = _RecordingPublisher()

    with direct_publishing(publisher):
        board.count = 3

    assert publisher.patches == ["Board"]


@pytest.mark.asyncio
async def test_agent_hands_readers_a_view_and_writers_the_state() -> None:
    """The two proxies used to be byte-identical; they must now differ in kind."""
    agent = BaseAgent(
        name="ro-test", transport=MemoryAgentTransport(), app_registry=AppRegistry()
    )
    board = _evented_board()
    agent.states["Board"] = board

    writeable = await agent.aget_write_proxy("Board")
    readable = await agent.aget_read_only_proxy("Board")

    assert writeable is board, "a writer gets the live state"
    assert readable is not board, "a reader must not get the writeable state"

    writeable.count = 4
    assert readable.count == 4, "the reader's view tracks the writer"

    with pytest.raises(ReadOnlyStateError):
        readable.count = 5


@pytest.mark.asyncio
async def test_readonly_annotation_reaches_an_actor_as_a_refusing_view() -> None:
    """End to end: ``ReadOnly[State]`` on a real actor parameter.

    ``is_read_only_state`` compared the annotation *instance* against the ``ReadOnly``
    type alias, which never matches, so such a parameter was classified as neither
    writeable nor read-only and dropped from the actor's kwargs entirely -- the call then
    failed with a missing argument. This drives the whole path: annotation -> classified
    read-only -> injected -> writes refused.
    """
    from rekuest_next import messages
    from rekuest_next.register import register
    from rekuest_next.state.types import ReadOnly

    agent = BaseAgent(
        name="ro-actor", transport=MemoryAgentTransport(), app_registry=AppRegistry()
    )
    transport = agent.transport
    board = _evented_board()
    agent.states["Board"] = board

    outcome: Dict[str, object] = {}

    def peek(reader: ReadOnly[Board]) -> int:
        """Read the state, then try to write it."""
        outcome["read"] = reader.count
        try:
            reader.count = 99
        except ReadOnlyStateError as e:
            outcome["refused"] = str(e)
        return 1

    register(
        peek,
        implementation_registry=agent.app_registry,
        structure_registry=agent.app_registry.structure_registry,
    )
    agent.collect_from_registry()

    board.count = 42
    await agent.process(
        messages.Assign(
            task="task-1",
            interface="peek",
            args={},
            implementation="impl-1",
            action="action-1",
            reference="ref-1",
            user="user-1",
            org="org-1",
        )
    )
    for _ in range(50):
        if "refused" in outcome:
            break
        await asyncio.sleep(0.01)

    assert outcome.get("read") == 42, (
        f"the actor must receive the read-only state, got {outcome} "
        f"(errors: {[c.error for c in transport.of_type(messages.Critical)]})"
    )
    assert "refused" in outcome, "the actor's write to a read-only state must be refused"
    assert board.count == 42, "the state must be unchanged"
