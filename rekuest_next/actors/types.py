"""Types for the actors module"""

import asyncio
from typing import (
    TYPE_CHECKING,
    Protocol,
    Self,
    runtime_checkable,
    Awaitable,
    Any,
    Literal,
)
from rekuest_next import messages
from rekuest_next.actors.policy import KEEP, DisconnectPolicy
from rekuest_next.agents.context import PreparedContextReturns, PreparedContextVariables
from rekuest_next.coercible_types import OptimisticCoercible
from rekuest_next.postmans.types import Postman
from rekuest_next.protocols import AnyFunction, AnyState
from rekuest_next.scalars import Identifier
from rekuest_next.state.publish import Patch
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.api.schema import (
    PortGroupInput,
    TestTargetInput,
    TrackInput,
    ValidatorInput,
)
from rekuest_next.definition.define import (
    AssignWidgetMap,
    DefinitionInput,
    EffectsMap,
    ReturnWidgetMap,
)
from typing import Optional, List, Dict, Sequence, Tuple, Callable
from dataclasses import dataclass


if TYPE_CHECKING:
    from rekuest_next.app import AppRegistry
    from rekuest_next.agents.lock import TaskLock


@dataclass
class AssignmentHook:
    """A hook that is called when an assignment is received. This can be used to
    modify the assignment before it is processed by the actor.
    """

    id: str
    kind: str
    hook: Callable[[messages.ToAgentMessage], Awaitable[None]]


@dataclass
class PreparedStateVariables:
    write_state_variables: Dict[str, str]
    read_only_variables: Dict[str, str]
    required_state_locks: Dict[str, list[str]]

    @property
    def count(self) -> int:
        """Get the amount of state variables."""
        return len(self.write_state_variables) + len(self.read_only_variables)

    @property
    def variable_keys(self) -> List[str]:
        """Get the keys of the state variables."""
        return list(self.write_state_variables.keys()) + list(
            self.read_only_variables.keys()
        )


@dataclass
class PreparedAppContextVariables:
    app_context_variables: Dict[str, str]

    @property
    def count(self) -> int:
        """Get the amount of state variables."""
        return len(self.app_context_variables)


@dataclass
class PreparedDependencyVariables:
    dependency_variables: Dict[str, Any]


@dataclass
class PreparedStateReturns:
    state_returns: Dict[int, str]

    @property
    def count(self) -> int:
        """Get the amount of state returns."""
        return len(self.state_returns)


@dataclass
class PreparedAppContextReturns:
    app_context_returns: Dict[int, str]

    @property
    def count(self) -> int:
        """Get the amount of app context returns."""
        return len(self.app_context_returns)


@dataclass
class ImplementationDetails:
    state_variables: PreparedStateVariables
    state_returns: PreparedStateReturns
    context_variables: PreparedContextVariables
    context_returns: PreparedContextReturns
    dependency_variables: PreparedDependencyVariables
    locks: Optional[List[str]] = None
    tracks: Optional[List["TrackInput"]] = None
    manipulates: Optional[List[str]] = None


@runtime_checkable
class Shelver(Protocol):
    """A protocol for mostly fullfield by the agent that is used to store data"""

    async def aput_on_shelve(
        self,
        identifier: Identifier,
        value: Any,  # noqa: ANN401
    ) -> str:  # noqa: ANN401
        """Put a value on the shelve and return the key. This is used to store
        values on the shelve."""
        ...

    async def aget_from_shelve(self, key: str) -> Any:  # noqa: ANN401
        """Get a value from the shelve. This is used to get values from the
        shelve."""
        ...


@runtime_checkable
class Capturable(Protocol):
    """The capture gate an actor's debug tooling coordinates on.

    Only :mod:`rekuest_next.actors.debug` touches this, which is why it is its own slice
    rather than part of what every actor sees.
    """

    capture_condition: asyncio.Condition
    capture_active: bool


@runtime_checkable
class LockHost(Protocol):
    """Reports lock acquisition, and resolves an actor's declared lock keys.

    Implemented by the agent and used by :class:`~rekuest_next.agents.lock.TaskLock`.
    """

    async def alock(self, key: str, task: str) -> None:
        """Report that a task has acquired a lock."""
        ...

    async def aunlock(self, key: str) -> None:
        """Report that a task has released a lock."""
        ...

    def get_locks_for_keys(self, keys: Sequence[str]) -> List["TaskLock"]:
        """Resolve the agent's task locks for the given lock keys."""
        ...


@runtime_checkable
class ActorContext(Shelver, LockHost, Capturable, Protocol):
    """Everything a running actor needs from the agent above it — and nothing more.

    Deliberately excludes the agent's own lifecycle (``aprovide`` / ``aconnect`` /
    ``aloop``): no actor calls those, and having them in one flat protocol made it read as
    though an actor could drive the agent it runs inside.
    """

    app_registry: "AppRegistry"

    @property
    def caller_postman(self) -> Postman:
        """The agent-as-caller postman, bound as ``current_postman`` while an actor runs.

        Declared as a property, not an attribute: implementations build it lazily, and a
        mutable protocol attribute is invariant, so a read-only property would not satisfy it.
        """
        ...

    async def asend(
        self, actor: "Actor", message: messages.FromAgentMessage
    ) -> None:
        """Send a message from an actor up to the agent, which forwards it onward."""
        ...

    async def aget_read_only_proxy(self, key: str) -> AnyState:  # noqa: ANN401
        """Get a state an actor only reads. See the note on the agent implementation:
        read-only is declarative, not enforced."""
        ...

    async def aget_write_proxy(self, key: str) -> AnyState:  # noqa: ANN401
        """Get a state an actor writes to."""
        ...

    async def aget_context(self, context: str) -> Any:  # noqa: ANN401
        """Get a context value registered with ``@context``."""
        ...

    def publish_patch(
        self, interface: str, patch: Patch, task_id: str | None = None
    ) -> None:
        """Publish a state patch. Satisfies ``state.publish.StateHolder``."""
        ...


@runtime_checkable
class AgentLifecycle(Protocol):
    """Driving the agent itself — what the composition root uses, not what actors use.

    Called only from :class:`~rekuest_next.rekuest.RekuestNext` and the FastAPI routes.
    """

    force: Optional[bool]
    """Kick any connection already registered for this agent and take over. ``None``
    defers to the transport's own build-time policy. Settable per run."""

    async def aprovide(self, context: Any) -> None:  # noqa: ANN401
        """Connect, then process messages until cancelled."""
        ...

    async def aconnect(self, context: Any = None, timeout: float | None = None) -> None:
        """Start the agent and connect, returning once the server acknowledges it."""
        ...

    async def aloop(self) -> None:
        """Process incoming messages after the agent has connected."""
        ...


@runtime_checkable
class Agent(ActorContext, AgentLifecycle, Protocol):
    """The whole agent surface: what actors need plus what drives it.

    Kept as the union of the slices above so every existing annotation and import keeps
    working. Prefer the narrowest slice that fits when writing new code —
    :class:`ActorContext` for anything an actor reaches, :class:`AgentLifecycle` for
    anything that starts or stops the agent.
    """


@runtime_checkable
class Actor(Protocol):
    """An actor is a function that takes a passport and a transport"""

    id: str
    """Stable identifier for this actor, recorded against the tasks it is running."""
    agent: Agent
    policy: DisconnectPolicy
    """What happens to this actor's work when the agent loses its control channel."""

    def has_running_tasks(self) -> bool:
        """Whether this actor currently has any assignment in flight."""
        ...

    def install_assignment_hook(self, task_id: str, hook: AssignmentHook) -> None:
        """Install an assignment hook for the current task.

        Args:
            task_id (str): The task to install the hook for.
            hook (AssignmentHook): The hook to install.
        """
        ...

    async def acancel(self) -> None:
        """Stop every assignment this actor is running.

        Called by the agent as it tears down, so in-flight work does not outlive the
        agent that owns it. Each cancelled task is reported to the backend.
        """
        ...

    async def acancel_for_policy(self, reason: str) -> int:
        """Stop every assignment this actor is running, per the disconnect policy.

        Distinct from :meth:`acancel`: it reports the given reason rather than the
        teardown wording, and prunes its task bookkeeping so a later liveness
        inquiry does not claim the killed work is still running. Returns how many
        assignments were stopped.
        """
        ...

    async def abreak(self, task_id: str) -> bool:
        """Break the actor. This method will break the actor and return None.
        This is used to break the actor"""
        ...

    async def asend(
        self: Self,
        message: messages.FromAgentMessage,
    ) -> None:
        """Send a message to the actor. This method will send a message to the
        actor and return None.
        """
        ...

    async def apass(
        self: Self,
        message: messages.ToAgentMessage,
    ) -> None:
        """Pass a message to the actor. This method will pass a message to the
        actor and return None.
        """
        ...

    async def acheck_task(
        self: Self,
        task_id: str,
    ) -> bool:
        """Check the task. This method will check the task and
        return None.
        """
        ...


@runtime_checkable
class ActorBuilder(Protocol):
    """An actor builder is a function that takes a passport and a transport
    and returns an actor. This method will create the actor and return it.
    """

    def __call__(
        self,
        agent: Agent,
    ) -> Actor:
        """Create the actor and return it. This method will create the actor and"""

        ...


@dataclass
class RegisterConfig:
    """Bundle of every option that shapes a registered function's definition and
    implementation.

    This is the single source of truth for the registration options. The public
    ``register`` decorator builds one of these from its keyword arguments and threads
    it — as a single object — down through ``register_func`` and the actifier, instead
    of re-listing ~20 parameters at every hop.

    The fields fall into two groups:

    * **definition-shaping** — unpacked by the actifier into ``prepare_definition``:
      ``name``, ``description``, ``widgets``, ``return_widgets``, ``effects``,
      ``validators``, ``collections``, ``port_groups``,
      ``is_test_for``, ``stateful``, ``version``, ``key``.
    * **implementation/actor-shaping** — used by the actifier's actor build and by
      ``register_func`` when constructing the ``ImplementationInput``:
      ``optimistics``, ``locks``, ``tracks``, ``manipulates``, ``in_process``,
      ``bypass_shrink``, ``bypass_expand``, ``auto_locks``, ``concurrency``,
      ``policy``.
    """

    # definition-shaping
    name: Optional[str] = None
    description: Optional[str] = None
    interface: Optional[str] = None
    widgets: Optional[AssignWidgetMap] = None
    return_widgets: Optional[ReturnWidgetMap] = None
    effects: Optional[EffectsMap] = None
    validators: Optional[Dict[str, List[ValidatorInput]]] = None
    collections: Optional[List[str]] = None
    port_groups: Optional[List[PortGroupInput]] = None
    is_test_for: Optional[List[TestTargetInput]] = None
    stateful: bool = False
    version: Optional[str] = None
    key: Optional[str] = None
    # implementation / actor-shaping
    optimistics: Optional[List[OptimisticCoercible]] = None
    locks: Optional[List[str]] = None
    tracks: Optional[List[TrackInput]] = None
    manipulates: Optional[List[str]] = None
    in_process: bool = False
    bypass_shrink: bool = False
    bypass_expand: bool = False
    auto_locks: bool = True
    concurrency: Literal["parallel", "serial"] = "serial"
    policy: DisconnectPolicy = KEEP


@runtime_checkable
class Actifier(Protocol):
    """An actifier is a function that takes a callable, a structure registry and a
    bundled :class:`RegisterConfig`, and returns a definition, implementation details
    and an actor builder.
    """

    def __call__(
        self,
        function: AnyFunction,
        structure_registry: StructureRegistry,
        config: Optional[RegisterConfig] = None,
    ) -> Tuple[DefinitionInput, ImplementationDetails, ActorBuilder]:
        """A function that will inspect the function and return a definition and
        an actor builder. This method will inspect the function and return a
        definition and an actor builder.
        """
        ...
