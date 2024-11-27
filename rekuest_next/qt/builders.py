import inspect
from typing import Any, Tuple, get_args, get_origin
from qtpy import QtCore
from koil.qt import QtCoro, QtGenerator, QtFuture, QtYielder
from rekuest_next.actors.functional import FunctionalFuncActor, FunctionalGenActor
from qtpy import QtWidgets
from rekuest_next.definition.registry import ActorBuilder
from rekuest_next.definition.define import prepare_definition, DefinitionInput
from rekuest_next.actors.types import ActorBuilder


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
        **actor_kwargs,
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

    async def on_unprovide(self) -> Any:
        return None

    def build(self, *args, **kwargs) -> Any:
        try:
            ac = FunctionalFuncActor(
                *args,
                **kwargs,
                structure_registry=self.structure_registry,
                assign=self.on_assign,
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
        **actor_kwargs,
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

    def build(self, *args, **kwargs) -> Any:
        try:
            ac = FunctionalFuncActor(
                *args,
                **kwargs,
                structure_registry=self.structure_registry,
                assign=self.on_assign,
                definition=self.definition,
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
        assign=None,
        *args,
        parent=None,
        structure_registry=None,
        definition=None,
        **actor_kwargs,
    ) -> None:
        super().__init__(*args, parent=parent)
        self.yielder = QtYielder(lambda *args, **kwargs: assign(*args, **kwargs))
        self.provisions = {}
        self.structure_registry = structure_registry
        self.actor_kwargs = actor_kwargs
        self.definition = definition

    async def on_assign(self, *args, **kwargs):
        async for i in self.yielder.aiterate(*args, **kwargs):
            yield i

    def build(self, *args, **kwargs) -> Any:
        try:
            ac = FunctionalGenActor(
                *args,
                **kwargs,
                structure_registry=self.structure_registry,
                assign=self.on_assign,
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

    def builder(*args, **kwargs) -> Any:
        return in_loop_instance.build(
            *args, **kwargs
        )  # build an actor for this inloop instance

    return definition, builder


def qtwithgeneratoractifier(
    function, structure_registry, parent: QtWidgets.QWidget = None, **kwargs
) -> ActorBuilder:
    """Qt Actifier

    The qt actifier wraps a function and returns a build that calls the function with
    its first parameter being a future that can be resolved within the qt loop
    """

    sig = inspect.signature(function)

    print(function)

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

    def builder(*args, **kwargs) -> Any:
        return in_loop_instance.build(
            *args, **kwargs
        )  # build an actor for this inloop instance

    return definition, builder
