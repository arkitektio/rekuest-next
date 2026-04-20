"""Builders for Qt actors.

This allow the async patterns of actors to extend to the Qt world.

"""

import inspect
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    get_args,
    get_origin,
)
from qtpy import QtCore, QtWidgets
from koil.qt import QtGenerator, QtFuture, qt_to_async
from rekuest_next.actors.functional import FunctionalFuncActor, FunctionalGenActor

from rekuest_next.agents.context import prepare_context_variables
from rekuest_next.agents.dependency import prepare_dependency_variables
from rekuest_next.definition.define import (
    AssignWidgetMap,
    EffectsMap,
    ReturnWidgetMap,
    prepare_definition,
    DefinitionInput,
)
from rekuest_next.actors.types import ActorBuilder, Agent, ImplementationDetails
from rekuest_next.protocols import AnyFunction
from rekuest_next.state.utils import prepare_state_variables
from rekuest_next.structures.registry import StructureRegistry


class QtInLoopBuilder(QtCore.QObject):
    """A function that takes a provision and an actor transport and returns an actor.

    The actor produces by this builder will be running in the same thread as the
    koil instance (aka, the thread that called the builder).

    Args:
        QtCore (_type_): _description_
    """

    def __init__(
        self,
        assign: Callable = None,
        *args,  # noqa: ANN002
        parent: QtWidgets.QWidget | None = None,
        structure_registry: StructureRegistry | None = None,
        definition: DefinitionInput = None,
        **actor_kwargs: dict,
    ) -> None:
        """Initialize the builder."""
        super().__init__(*args, parent=parent)
        self.wrapped_function = assign
        self.coro = qt_to_async(self.qt_assign)
        self.provisions = {}
        self.structure_registry = structure_registry
        self.actor_kwargs = actor_kwargs
        self.definition = definition

    def qt_assign(self, future: QtFuture[Any], *args, **kwargs) -> None:
        """Assigns the future to the coroutine."""
        future.resolve(self.wrapped_function(*args, **kwargs))

    async def on_assign(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        """Runs in the same thread as the koil instance."""

        return await self.coro.acall(**kwargs)

    def build(self, agent: Agent) -> "FunctionalFuncActor":
        """Builds the actor."""
        try:
            ac = FunctionalFuncActor(
                agent=agent,
                structure_registry=self.structure_registry,
                assign=self.on_assign,
                definition=self.definition,
                **self.actor_kwargs,
            )
            return ac
        except Exception as e:
            raise e


class QtFutureBuilder(QtCore.QObject):
    """A function that takes a provision and an actor transport and returns an actor.

    The actor produces by this builder will be running in the same thread as the
    koil instance (aka, the thread that called the builder).

    Args:
        QtCore (_type_): _description_
    """

    def __init__(
        self,
        assign: Callable = None,
        *args,  # noqa: ANN002
        parent: QtWidgets.QWidget | None = None,
        structure_registry: StructureRegistry | None = None,
        definition: DefinitionInput = None,
        **actor_kwargs: dict,
    ) -> None:
        """Initialize the builder."""
        super().__init__(*args, parent=parent)
        self.coro = qt_to_async(lambda *args, **kwargs: assign(*args, **kwargs))
        self.provisions = {}
        self.structure_registry = structure_registry
        self.actor_kwargs = actor_kwargs
        self.definition = definition

    async def on_assign(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        """Runs in the same thread as the koil instance."""
        x = await self.coro.acall(*args, **kwargs)
        return x

    def build(self, agent: Agent) -> "FunctionalFuncActor":
        """Builds the actor."""
        try:
            ac = FunctionalFuncActor(
                agent=agent,
                structure_registry=self.structure_registry,
                assign=self.on_assign,
                definition=self.definition,
                **self.actor_kwargs,
            )
            return ac
        except Exception as e:
            raise e


class QtGeneratorBuilder(QtCore.QObject):
    """A function that takes a provision and an actor transport and returns an actor.

    The actor produces by this builder will be running in the same thread as the
    koil instance (aka, the thread that called the builder).

    Args:
        QtCore (_type_): _description_
    """

    def __init__(
        self,
        assign: Callable = None,
        *args,  # noqa: ANN002
        parent: QtWidgets.QWidget | None = None,
        structure_registry: StructureRegistry | None = None,
        definition: DefinitionInput | None = None,
        **actor_kwargs: dict,
    ) -> None:
        """Initialize the builder."""
        super().__init__(*args, parent=parent)
        self.yielder = QtYielder(lambda *args, **kwargs: assign(*args, **kwargs))
        self.provisions = {}
        self.structure_registry = structure_registry
        self.actor_kwargs = actor_kwargs
        self.definition = definition

    async def on_assign(self, *args, **kwargs) -> AsyncGenerator[Any, None]:  # noqa: ANN002, ANN003
        """Runs in the same thread as the koil instance."""
        async for i in self.yielder.aiterate(*args, **kwargs):
            yield i

    def build(self, agent: Agent) -> "FunctionalGenActor":
        """Builds the actor."""
        try:
            ac = FunctionalGenActor(
                agent=agent,
                structure_registry=self.structure_registry,
                assign=self.on_assign,
                definition=self.definition,
                **self.actor_kwargs,
            )
            return ac
        except Exception as e:
            raise e


def qtinloopactifier(
    function: AnyFunction,
    structure_registry: StructureRegistry,
    parent: QtWidgets.QWidget = None,
    bypass_shrink: bool = False,
    bypass_expand: bool = False,
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
    auto_locks: bool = True,
    locks: Optional[List[str]] = None,
    version: Optional[str] = None,
    key: Optional[str] = None,
    actor_class: Optional[type] = None,
) -> Tuple[DefinitionInput, ImplementationDetails, ActorBuilder]:
    """Reactify a function

    This function takes a callable (of type async or sync function or generator) and
    returns a builder function that creates an actor that makes the function callable
    from the rekuest server.
    """

    state_variables, state_returns = prepare_state_variables(function)
    context_variables, context_returns = prepare_context_variables(function)
    dependency_variables = prepare_dependency_variables(function)

    if not locks and auto_locks:
        locks = []
        for lock in context_variables.required_context_locks.values():
            locks.extend(lock)
        for lock in state_variables.required_state_locks.values():
            locks.extend(lock)
        locks = list(set(locks))

    if state_variables:
        stateful = True

    implementation_details = ImplementationDetails(
        state_variables=state_variables,
        state_returns=state_returns,
        context_variables=context_variables,
        context_returns=context_returns,
        dependency_variables=dependency_variables,
        locks=locks,
    )

    definition = prepare_definition(
        function,
        structure_registry,
        widgets=widgets,
        interfaces=interfaces,
        port_groups=port_groups,
        collections=collections,
        stateful=stateful,
        validators=validators,
        effects=effects,
        is_test_for=is_test_for,
        name=name,
        description=description,
        return_widgets=return_widgets,
        logo=logo,
        key=key,
        version=version,
    )

    actor_attributes: dict[str, Any] = {
        "expand_inputs": not bypass_expand,
        "shrink_outputs": not bypass_shrink,
        "state_variables": state_variables,
        "state_returns": state_returns,
        "context_variables": context_variables,
        "context_returns": context_returns,
        "dependency_variables": dependency_variables,
        "locks": locks,
    }
    """Qt Actifier

    The qt actifier wraps a function and returns a builder that will create an actor
    that runs in the same thread as the Qt instance, enabling the use of Qt widgets
    and signals.
    """

    definition = prepare_definition(function, structure_registry)

    in_loop_instance = QtInLoopBuilder(
        parent=parent,
        assign=function,
        structure_registry=structure_registry,
        definition=definition,
        **actor_attributes,
    )

    return definition, implementation_details, in_loop_instance.build


def qtwithfutureactifier(
    function: Callable,
    structure_registry: StructureRegistry,
    parent: QtWidgets.QWidget = None,
    **kwargs: dict,
) -> ActorBuilder:
    """Qt Actifier

    The qt actifier wraps a function and returns a build that calls the function with
    its first parameter being a future that can be resolved within the qt loop
    """

    sig = inspect.signature(function)

    if len(sig.parameters) == 0:
        raise ValueError(
            f"The function  {function} you are trying to register with a generator actifier must have at least one parameter, the Generator"
        )

    first = sig.parameters[list(sig.parameters.keys())[0]].annotation

    if not get_origin(first) == QtFuture:
        raise ValueError(
            f"The function {function}  you are trying to register needs to have a QtGenerator as its first parameter"
        )

    return_params = get_args(first)

    if len(return_params) == 0:
        raise ValueError(
            "If you are using a QtGenerator as the first parameter, you need to provide the return type of the generator as a type hint. E.g `QtGenerator[int]`"
        )

    definition = prepare_definition(
        function,
        structure_registry,
        omitfirst=1,
        return_annotations=return_params,
        **kwargs,
    )

    in_loop_instance = QtFutureBuilder(
        parent=parent,
        assign=function,
        structure_registry=structure_registry,
        definition=definition,
    )

    return definition, in_loop_instance.build


def qtwithgeneratoractifier(
    function: Callable,
    structure_registry: StructureRegistry,
    parent: QtWidgets.QWidget = None,
    **kwargs: dict,
) -> Tuple[DefinitionInput, ActorBuilder]:
    """Qt Actifier

    The qt actifier wraps a function and returns a build that calls the function with
    its first parameter being a future that can be resolved within the qt loop
    """

    sig = inspect.signature(function)

    if len(sig.parameters) == 0:
        raise ValueError(
            "The function you are trying to register with a generator actifier must have at least one parameter, the Generator"
        )

    first = sig.parameters[list(sig.parameters.keys())[0]].annotation

    if not get_origin(first) == QtGenerator:
        raise ValueError(
            "The function needs to have a QtGenerator as its first parameter"
        )

    return_params = get_args(first)

    if len(return_params) == 0:
        raise ValueError(
            "If you are using a QtGenerator as the first parameter, you need to provide the return type of the generator as a type hint. E.g `QtGenerator[int]`"
        )

    definition = prepare_definition(
        function,
        structure_registry,
        omitfirst=1,
        return_annotations=return_params,
        **kwargs,
    )

    in_loop_instance = QtGeneratorBuilder(
        parent=parent,
        assign=function,
        structure_registry=structure_registry,
        definition=definition,
    )
    # build an actor for this inloop instance

    return definition, in_loop_instance.build
