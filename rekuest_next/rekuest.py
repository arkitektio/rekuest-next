"""The base client for rekuest next"""

from typing import Optional, TypeVar
from koil.helpers import unkoil_task
from koil import KoilFuture
from pydantic import Field
from rekuest_next.agents.hooks.background import background
from rekuest_next.coercible_types import DependencyCoercible
from rekuest_next.protocols import AnyFunction, BackgroundFunction, StartupFunction
from rekuest_next.rath import RekuestNextRath
from rekuest_next.agents.extensions.default import DefaultExtension
from rekuest_next.actors.types import Actifier, Agent
from rekuest_next.postmans.types import Postman
from koil import unkoil
from koil.composition import Composition

from typing import (
    Dict,
    List,
    Tuple,
)

from rekuest_next.actors.actify import reactify
from rekuest_next.actors.sync import SyncGroup
from rekuest_next.actors.types import ActorBuilder, OnProvide, OnUnprovide
from rekuest_next.definition.registry import (
    DefinitionRegistry,
    get_default_definition_registry,
)
from rekuest_next.structures.default import get_default_structure_registry
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.register import register_func
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
        function: AnyFunction,
        actifier: Actifier = reactify,
        interface: Optional[str] = None,
        stateful: bool = False,
        widgets: Optional[Dict[str, AssignWidgetInput]] = None,
        dependencies: Optional[List[DependencyCoercible]] = None,
        interfaces: Optional[List[str]] = None,
        collections: Optional[List[str]] = None,
        port_groups: Optional[List[PortGroupInput]] = None,
        effects: Optional[Dict[str, List[EffectInput]]] = None,
        is_test_for: Optional[List[str]] = None,
        logo: Optional[str] = None,
        on_provide: Optional[OnProvide] = None,
        on_unprovide: Optional[OnUnprovide] = None,
        validators: Optional[Dict[str, List[ValidatorInput]]] = None,
        structure_registry: Optional[StructureRegistry] = None,
        definition_registry: Optional[DefinitionRegistry] = None,
        in_process: bool = False,
        dynamic: bool = False,
        sync: Optional[SyncGroup] = None,
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
            definition_registry (Optional[DefinitionRegistry], optional): Custom definition registry instance.
            in_process (bool, optional): Execute actor in the same process.
            dynamic (bool, optional): Whether the actor definition is subject to change dynamically.
            sync (Optional[SyncGroup], optional): Optional synchronization group.

        Returns:
            function: A decorator that registers the given function or actor.
        """

        default_extension = self.agent.extension_registry.get("default")
        assert default_extension is not None, "Default extension not found"
        assert isinstance(default_extension, DefaultExtension), (
            "Default is not a DefaultExtension"
        )

        return register_func(
            function,
            structure_registry=structure_registry or self.structure_registry,
            definition_registry=default_extension.definition_registry,
            actifier=actifier,
            interface=interface,
            stateful=stateful,
            widgets=widgets,
            dependencies=dependencies,
            interfaces=interfaces,
            collections=collections,
            port_groups=port_groups,
            effects=effects,
            is_test_for=is_test_for,
            logo=logo,
            on_provide=on_provide,
            on_unprovide=on_unprovide,
            validators=validators,
            in_process=in_process,
            dynamic=dynamic,
            sync=sync,
        )

    def register_startup(
        self, function: StartupFunction, name: str | None = None
    ) -> None:
        """Register a startup function that will be called when the agent starts.

        Args:
            function (AnyFunction): The startup function to register.
        """
        startup(
            function, name=name or function.__name__, registry=self.agent.hook_registry
        )

    def register_background(
        self, function: BackgroundFunction, name: str | None = None
    ) -> None:
        """Register a background function that will be run in the background.

        Args:
            function (BackgroundFunction): The background function to register.
        """
        background(
            function, name=name or function.__name__, registry=self.agent.hook_registry
        )

    def run(self, instance_id: str | None = None) -> None:
        """
        Run the application.
        """
        return unkoil(self.arun, instance_id=instance_id)

    def run_detached(self, instance_id: str | None = None) -> KoilFuture[None]:
        """
        Run the application detached.
        """
        return unkoil_task(self.arun, instance_id=instance_id)

    async def arun(self, instance_id: str | None = None) -> None:
        """
        Run the application.
        """
        await self.agent.aprovide(instance_id=instance_id)

    async def arun_tests(self, instance_id: str | None = None) -> None:
        """
        Run the application tests.
        """
        await self.agent.atest(instance_id=instance_id)
