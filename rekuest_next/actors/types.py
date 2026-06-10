"""Types for the actors module"""

from typing import TYPE_CHECKING, Protocol, Self, runtime_checkable, Awaitable, Any
from rekuest_next import messages
from rekuest_next.agents.context import PreparedContextReturns, PreparedContextVariables
from rekuest_next.coercible_types import OptimisticCoercible
from rekuest_next.protocols import AnyFunction, AnyState
from rekuest_next.scalars import Identifier
from rekuest_next.state.publish import Patch
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.api.schema import (
    PortGroupInput,
    TrackInput,
    ValidatorInput,
)
from rekuest_next.definition.define import (
    AssignWidgetMap,
    DefinitionInput,
    EffectsMap,
    ReturnWidgetMap,
)
from typing import Optional, List, Dict, Tuple, Callable
from pydantic import BaseModel, Field
import uuid
from dataclasses import dataclass


if TYPE_CHECKING:
    from rekuest_next.app import AppRegistry


@dataclass
class AssignmentHook:
    """A hook that is called when an assignment is received. This can be used to
    modify the assignment before it is processed by the actor.
    """

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
    def required_locks_amount(self) -> int:
        """Get the amount of locks."""
        return len(self.required_state_locks)

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


class Passport(BaseModel):
    """The passport of the actor. This is used to identify the actor and"""

    instance_id: str
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


@runtime_checkable
class ImplementationDetailsProtocol(Protocol):
    state_variables: Any
    state_returns: Any
    context_variables: Any
    context_returns: Any
    locks: Optional[List[str]]


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
class Agent(Protocol):
    """A protocol for the agent that is used to send messages to the agent."""

    app_registry: "AppRegistry"
    instance_id: str

    async def alock(self, key: str, assignation: str) -> None:
        """A function to acquire a lock on the agent. This is used to acquire
        locks on the agent."""
        ...

    async def aunlock(self, key: str) -> None:
        """A function to release a lock on the agent. This is used to release
        locks on the agent."""
        ...

    async def asend(
        self: "Agent", actor: "Actor", message: messages.FromAgentMessage
    ) -> None:
        """A function to send a message to the agent. This is used to send messages
        to the agent from the actor."""

        ...

    async def aget_read_only_proxy(self, interface: str) -> AnyState:  # noqa: ANN401
        """Get a readonly state from the agent. This is used to get readonly states from the
        agent from the actor."""
        ...

    async def aget_write_proxy(self, interface: str) -> AnyState:  # noqa: ANN401
        """Get a writeable state from the agent. This is used to get writeable states from the
        agent from the actor."""
        ...

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

    async def aget_state(self, interface: str) -> AnyState:  # noqa: ANN401
        """Get a state from the agent. This is used to get states from the
        agent from the actor."""
        ...

    async def aget_context(self, context: str) -> Any:  # noqa: ANN401
        """Get a context from the agent. This is used to get contexts from the
        agent from the actor."""
        ...

    async def aprovide(self, context: Any) -> None:
        """Provide the provision. This method will provide the provision and
        return None.
        """
        ...

    def publish_patch(self, instance: AnyState, patch: Patch) -> None:
        """Publish a patch to the agent. This is used to publish patches to the
        agent from the actor."""
        ...


@runtime_checkable
class Actor(Protocol):
    """An actor is a function that takes a passport and a transport"""

    agent: Agent

    def install_assignment_hook(self, assignation: str, hook: AssignmentHook) -> None:
        """Install an assignment hook for the current assignation.

        Args:
            assignation (str): The assignation to install the hook for.
            hook (AssignmentHook): The hook to install.
        """
        ...

    async def abreak(self, assignation_id: str) -> bool:
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

    async def acheck_assignation(
        self: Self,
        assignation_id: str,
    ) -> bool:
        """Check the assignation. This method will check the assignation and
        return None.
        """
        ...

    async def apublish_state(self: Self, state: AnyState) -> None:
        """A function to publish the state of the actor. This is used to publish the
        state of the actor to the agent.

        Args:
            state (AnyState): The state to publish.
        """
        ...


@runtime_checkable
class OnProvide(Protocol):
    """An on_provide is a function gets call when the actors gets first started"""

    def __call__(
        self,
        passport: Passport,
    ) -> Awaitable[Any]:
        """Provide the provision. This method will provide the provision and"""
        ...


@runtime_checkable
class OnUnprovide(Protocol):
    """An on unprovide is a function gets call when the actors gets kills"""

    def __call__(self) -> Awaitable[Any]:
        """Unprovide the provision. This method will unprovide the provision and"""
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
      ``validators``, ``collections``, ``port_groups``, ``interfaces``,
      ``is_test_for``, ``logo``, ``stateful``, ``version``, ``key``.
    * **implementation/actor-shaping** — used by the actifier's actor build and by
      ``register_func`` when constructing the ``ImplementationInput``: ``dynamic``,
      ``optimistics``, ``locks``, ``tracks``, ``manipulates``, ``in_process``,
      ``bypass_shrink``, ``bypass_expand``, ``auto_locks``.
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
    interfaces: Optional[List[str]] = None
    is_test_for: Optional[List[str]] = None
    logo: Optional[str] = None
    stateful: bool = False
    version: Optional[str] = None
    key: Optional[str] = None
    # implementation / actor-shaping
    dynamic: bool = False
    optimistics: Optional[List[OptimisticCoercible]] = None
    locks: Optional[List[str]] = None
    tracks: Optional[List[TrackInput]] = None
    manipulates: Optional[List[str]] = None
    in_process: bool = False
    bypass_shrink: bool = False
    bypass_expand: bool = False
    auto_locks: bool = True


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
