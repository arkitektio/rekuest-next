"""Types for the actors module"""

import asyncio
from typing import TYPE_CHECKING, Protocol, Self, runtime_checkable, Awaitable, Any
from rekuest_next import messages
from rekuest_next.actors.sync import SyncGroup
from rekuest_next.protocols import AnyFunction, AnyState
from rekuest_next.scalars import Identifier
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.api.schema import PortGroupInput, ValidatorInput
from rekuest_next.definition.define import (
    AssignWidgetMap,
    DefinitionInput,
    EffectsMap,
    ReturnWidgetMap,
)
from typing import Optional, List, Dict, Tuple
from pydantic import BaseModel, Field
import uuid

if TYPE_CHECKING:
    from rekuest_next.agents.registry import ExtensionRegistry
    from rekuest_next.agents.hooks.registry import HooksRegistry


class Passport(BaseModel):
    """The passport of the actor. This is used to identify the actor and"""

    instance_id: str
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


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

    hook_registry: "HooksRegistry"
    extension_registry: "ExtensionRegistry"
    instance_id: str
    capture_condition: asyncio.Condition
    capture_active: bool

    async def asend(
        self: "Agent", actor: "Actor", message: messages.FromAgentMessage
    ) -> None:
        """A function to send a message to the agent. This is used to send messages
        to the agent from the actor."""

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

    async def apublish_state(self, state: AnyState) -> None:  # noqa: ANN401
        """Publish a state to the agent. This is used to publish states to the
        agent from the actor."""
        ...

    async def aget_state(self, interface: str) -> AnyState:  # noqa: ANN401
        """Get a state from the agent. This is used to get states from the
        agent from the actor."""
        ...

    async def aget_context(self, context: str) -> Any:  # noqa: ANN401
        """Get a context from the agent. This is used to get contexts from the
        agent from the actor."""
        ...

    async def aprovide(
        self,
        instance_id: str | None = None,
    ) -> None:
        """Provide the provision. This method will provide the provision and
        return None.
        """
        ...

    async def atest(
        self,
        instance_id: str | None = None,
    ) -> None:
        """Run the tests. This method will run the tests and return None."""
        ...


@runtime_checkable
class Actor(Protocol):
    """An actor is a function that takes a passport and a transport"""

    agent: Agent

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


@runtime_checkable
class Actifier(Protocol):
    """An actifier is a function that takes a callable and a structure registry
    as well as optional arguments

    """

    def __call__(
        self,
        function: AnyFunction,
        structure_registry: StructureRegistry,
        bypass_shrink: bool = False,
        bypass_expand: bool = False,
        on_provide: Optional[OnProvide] = None,
        on_unprovide: Optional[OnUnprovide] = None,
        description: str | None = None,
        stateful: bool = False,
        validators: Optional[Dict[str, List[ValidatorInput]]] = None,
        collections: List[str] | None = None,
        effects: EffectsMap | None = None,
        port_groups: Optional[List[PortGroupInput]] = None,
        is_test_for: Optional[List[str]] = None,
        widgets: AssignWidgetMap | None = None,
        return_widgets: ReturnWidgetMap | None = None,
        interfaces: List[str] | None = None,
        in_process: bool = False,
        logo: str | None = None,
        name: str | None = None,
        sync: Optional[SyncGroup] = None,
    ) -> Tuple[DefinitionInput, ActorBuilder]:
        """A function that will inspect the function and return a definition and
        an actor builder. This method will inspect the function and return a
        definition and an actor builder.
        """
        ...
