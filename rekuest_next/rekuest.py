"""The base client for rekuest next"""

from typing import Optional, TypeVar
from koil.helpers import unkoil_task
from koil import KoilFuture
from pydantic import Field
from rekuest_next.agents.hooks.background import background
from rekuest_next.protocols import AnyFunction, BackgroundFunction, StartupFunction
from rekuest_next.rath import RekuestNextRath
from rekuest_next.actors.types import Actifier, Agent
from rekuest_next.postmans.types import Postman
from koil import unkoil
from koil.composition import Composition

from typing import (
    Dict,
    List,
    Tuple,
    Any,
)
from rekuest_next.actors.actify import reactify
from rekuest_next.actors.types import ActorBuilder
from rekuest_next.structures.default import get_default_structure_registry
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.register import register, register_func
from rekuest_next.agents.hooks.startup import startup
from rekuest_next.api.schema import (
    AssignWidgetInput,
    DefinitionInput,
    PortGroupInput,
    EffectInput,
    ValidatorInput,
)


T = TypeVar("T", bound=AnyFunction)


class RekuestNext(Composition):
    """The main rekuest next client class"""

    structure_registry: StructureRegistry = Field(
        default_factory=get_default_structure_registry
    )
    rath: RekuestNextRath
    agent: Agent
    postman: Postman

    def register(
        self,
        *args,
        **kwargs,
    ) -> Tuple[DefinitionInput, ActorBuilder]:
        """Register a function or actor with optional configuration parameters.

        This overload supports usage of `@register(...)` as a configurable decorator.

        Args:
            func (T): Function to register.
            actifier (Actifier, optional): Function to wrap callables into actors.
            interface (Optional[str], optional): Interface name override.
            stateful (bool, optional): Whether the actor maintains internal state.
            widgets (Optional[Dict[str, AssignWidgetInput]], optional): Mapping of parameter names to widgets.
            dependencies (Optional[List[DependencyInput]], optional): List of external dependencies.
            interfaces (Optional[List[str]], optional): Additional interfaces implemented.
            collections (Optional[List[str]], optional): Groupings for organizational purposes.
            port_groups (Optional[List[PortGroupInput]], optional): Port group assignments.
            effects (Optional[Dict[str, List[EffectInput]]], optional): Mapping of effects per port.
            is_test_for (Optional[List[str]], optional): Interfaces this function serves as a test for.
            logo (Optional[str], optional): URL or identifier for the actor's logo.
            on_provide (Optional[OnProvide], optional): Hook triggered when actor is provided.
            on_unprovide (Optional[OnUnprovide], optional): Hook triggered when actor is unprovided.
            validators (Optional[Dict[str, List[ValidatorInput]]], optional): Input validation rules.
            structure_registry (Optional[StructureRegistry], optional): Custom structure registry instance.
            implementation_registry (Optional[DefinitionRegistry], optional): Custom implementation registry instance.
            in_process (bool, optional): Execute actor in the same process.
            dynamic (bool, optional): Whether the actor definition is subject to change dynamically.
            sync (Optional[SyncGroup], optional): Optional synchronization group.

        Returns:
            function: A decorator that registers the given function or actor.
        """

        return register(
            *args,
            implementation_registry=self.agent.app_registry,
            structure_registry=self.agent.app_registry.structure_registry,
            **kwargs,
        )

    def register_startup(
        self, function: StartupFunction, name: str | None = None
    ) -> None:
        """Register a startup function that will be called when the agent starts.

        Args:
            function (AnyFunction): The startup function to register.
        """
        startup(
            function,
            name=name or function.__name__,
            registry=self.agent.app_registry.hooks_registry,
        )

    def register_background(
        self, function: BackgroundFunction, name: str | None = None
    ) -> None:
        """Register a background function that will be run in the background.

        Args:
            function (BackgroundFunction): The background function to register.
        """
        background(
            function,
            name=name or function.__name__,
            registry=self.agent.app_registry.hooks_registry,
        )

    def register_blok(
        self,
        name: str | None = None,
        component: Optional[str] = None,
        description: Optional[str] = None,
        demo_state: Dict[str, Any] | None = None,
    ) -> None:
        """Register a blok with the given name and optional JSX content.

        Args:
            name (str | None): The name of the blok. If None, the function name will be used.
            component (Optional[str]): Optional component content to associate with the blok.
            description (Optional[str]): Optional description for the blok.
            demo_state (Dict[str, Any] | None): Optional demo state for the blok.
        """
        self.agent.app_registry.register_blok(
            name=name,
            component=component,
            description=description,
            demo_state=demo_state,
        )

    def state(self, *args, **kwargs):
        """Decorator to define a state class."""
        from rekuest_next.state.decorator import state

        return state(*args, **kwargs)

    def run(self, context: Any | None = None) -> None:
        """
        Run the application.
        """
        return unkoil(self.arun, context=context)

    def run_detached(self, context: Any | None = None) -> KoilFuture[None]:
        """
        Run the application detached.
        """
        return unkoil_task(self.arun, context=context)

    async def arun(self, context: Any | None = None) -> None:
        """
        Run the application.
        """
        await self.agent.aprovide(context=context)

    async def arun_tests(self, context: Any | None = None) -> None:
        """
        Run the application tests.
        """
        await self.agent.atest(context=context)
