from typing import Any, Tuple
from qtpy import QtCore
from rekuest_next.agents.transport.base import AgentTransport
from rekuest_next.messages import Provision
from koil.qt import QtCoro
from rekuest_next.actors.functional import FunctionalFuncActor
from qtpy import QtWidgets
from rekuest_next.definition.registry import ActorBuilder
from rekuest_next.definition.define import prepare_definition, DefinitionInput
from rekuest_next.actors.types import ActorBuilder, Passport
from rekuest_next.collection.collector import ActorCollector
from rekuest_next.actors.transport.types import ActorTransport


class QtInLoopBuilder(QtCore.QObject):
    """A function that takes a provision and an actor transport and returns an actor.

    The actor produces by this builder will be running in the same thread as the
    koil instance (aka, the thread that called the builder).

    Args:
        QtCore (_type_): _description_
    """

    def __init__(
        self,
        assign=None,
        *args,
        parent=None,
        structure_registry=None,
        definition=None,
        **actor_kwargs
    ) -> None:
        super().__init__(*args, parent=parent)
        self.coro = QtCoro(
            lambda *args, **kwargs: assign(*args, **kwargs), autoresolve=True
        )
        self.provisions = {}
        self.structure_registry = structure_registry
        self.actor_kwargs = actor_kwargs
        self.definition = definition

    async def on_assign(self, *args, **kwargs) -> None:
        return await self.coro.acall(*args, **kwargs)

    async def on_provide(self, provision: Provision) -> Any:
        return None

    async def on_unprovide(self) -> Any:
        return None

    def build(self, *args, **kwargs) -> Any:
        try:
            ac = FunctionalFuncActor(
                *args,
                **kwargs,
                structure_registry=self.structure_registry,
                assign=self.on_assign,
                on_provide=self.on_provide,
                on_unprovide=self.on_unprovide,
                definition=self.definition,
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
        assign=None,
        *args,
        parent=None,
        structure_registry=None,
        definition=None,
        **actor_kwargs
    ) -> None:
        super().__init__(*args, parent=parent)
        self.coro = QtCoro(
            lambda *args, **kwargs: assign(*args, **kwargs), autoresolve=False
        )
        self.provisions = {}
        self.structure_registry = structure_registry
        self.actor_kwargs = actor_kwargs
        self.definition = definition

    async def on_assign(self, *args, **kwargs) -> None:
        x = await self.coro.acall(*args, **kwargs)
        return x

    async def on_provide(self, provision: Provision) -> Any:
        return None

    async def on_unprovide(self) -> Any:
        return None

    def build(self, *args, **kwargs) -> Any:
        try:
            ac = FunctionalFuncActor(
                *args,
                **kwargs,
                structure_registry=self.structure_registry,
                assign=self.on_assign,
                on_provide=self.on_provide,
                on_unprovide=self.on_unprovide,
                definition=self.definition,
            )
            return ac
        except Exception as e:
            raise e


def qtinloopactifier(
    function, structure_registry, parent: QtWidgets.QWidget = None, **kwargs
) -> Tuple[DefinitionInput, ActorBuilder]:
    """Qt Actifier

    The qt actifier wraps a function and returns a builder that will create an actor
    that runs in the same thread as the Qt instance, enabling the use of Qt widgets
    and signals.
    """

    definition = prepare_definition(function, structure_registry, **kwargs)

    in_loop_instance = QtInLoopBuilder(
        parent=parent,
        assign=function,
        structure_registry=structure_registry,
        definition=definition,
    )

    def builder(*args, **kwargs) -> Any:
        return in_loop_instance.build(
            *args, **kwargs
        )  # build an actor for this inloop instance

    return definition, builder


def qtwithfutureactifier(
    function, structure_registry, parent: QtWidgets.QWidget = None, **kwargs
) -> ActorBuilder:
    """Qt Actifier

    The qt actifier wraps a function and returns a build that calls the function with
    its first parameter being a future that can be resolved within the qt loop
    """

    definition = prepare_definition(function, structure_registry, omitfirst=1, **kwargs)

    in_loop_instance = QtFutureBuilder(
        parent=parent,
        assign=function,
        structure_registry=structure_registry,
        definition=definition,
    )

    def builder(*args, **kwargs) -> Any:
        return in_loop_instance.build(
            *args, **kwargs
        )  # build an actor for this inloop instance

    return definition, builder
