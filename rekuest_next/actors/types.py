"""Types for the actors module"""

from typing import Protocol, Self, runtime_checkable, Callable, Awaitable, Any
from rekuest_next import messages
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.api.schema import PortGroupInput
from rekuest_next.definition.define import DefinitionInput
from typing import Optional, List, Dict, Tuple
from pydantic import BaseModel, Field
import uuid


class Passport(BaseModel):
    """The passport of the actor. This is used to identify the actor and"""

    instance_id: str
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


@runtime_checkable
class Shelver(Protocol):
    """A protocol for mostly fullfield by the agent that is used to store data"""

    async def aput_on_shelve(
        self,
        identifier: str,
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

    async def asend(self: "Agent", actor: "Actor", message: messages.Assign) -> None:
        """A function to send a message to the agent. This is used to send messages
        to the agent from the actor."""

        ...


@runtime_checkable
class Actor(Protocol):
    """An actor is a function that takes a passport and a transport"""

    agent: Agent

    async def asend(
        self: Self,
        message: messages.FromAgentMessage,
    ) -> None:
        """Send a message to the actor. This method will send a message to the
        actor and return None.
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
        contexts: Dict[str, Any],
        proxies: Dict[str, Any],
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
        function: Callable,
        structure_registry: StructureRegistry,
        port_groups: Optional[List[PortGroupInput]] = None,
        is_test_for: Optional[List[str]] = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Tuple[DefinitionInput, ActorBuilder]:
        """A function that will inspect the function and return a definition and
        an actor builder. This method will inspect the function and return a
        definition and an actor builder.
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
