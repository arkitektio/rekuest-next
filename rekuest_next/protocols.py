from typing import Any, Awaitable, Protocol, Union, runtime_checkable


@runtime_checkable
class AnyFunction(Protocol):
    """A function that takes a passport and a transport and returns an actor.
    This method will create the actor and return it.
    """

    def __call__(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN001, ANN401
        """Create the actor and return it. This method will create the actor and
        return it.
        """
        ...

    @property
    def __name__(self) -> str:
        """Get the name of the function. This method will return the name of the
        function.
        """
        ...


@runtime_checkable
class AnyState(Protocol):
    """A function that takes a passport and a transport and returns an actor.
    This method will create the actor and return it.
    """

    pass


@runtime_checkable
class AnyContext(Protocol):
    """A function that takes a passport and a transport and returns an actor.
    This method will create the actor and return it.
    """

    pass


@runtime_checkable
class BackgroundFunction(Protocol):
    """A function that takes a passport and a transport and returns an actor.
    This method will create the actor and return it.
    """

    def __call__(self, *args: Any, **kwargs: Any) -> Awaitable[None] | None:
        """Create the actor and return it. This method will create the actor and
        return it.
        """
        ...

    @property
    def __name__(self) -> str:
        """Get the name of the function. This method will return the name of the
        function.
        """
        ...


@runtime_checkable
class AsyncBackgroundFunction(Protocol):
    """A function that takes a passport and a transport and returns an actor.
    This method will create the actor and return it.
    """

    def __call__(self, *args: Any, **kwargs: Any) -> Awaitable[None]:
        """Create the actor and return it. This method will create the actor and
        return it.
        """
        ...

    @property
    def __name__(self) -> str:
        """Get the name of the function. This method will return the name of the
        function.
        """
        ...


@runtime_checkable
class ThreadedBackgroundFunction(Protocol):
    """A function that takes a passport and a transport and returns an actor.
    This method will create the actor and return it.
    """

    def __call__(
        self, *args: Union[AnyState, AnyContext], **kwargs: Union[AnyState, AnyContext]
    ) -> None:
        """Create the actor and return it. This method will create the actor and
        return it.
        """
        ...

    @property
    def __name__(self) -> str:
        """Get the name of the function. This method will return the name of the
        function.
        """
        ...


@runtime_checkable
class StartupFunction(Protocol):
    """A function that takes a passport and a transport and returns an actor.
    This method will create the actor and return it.
    """

    def __call__(
        self, instance_id: str
    ) -> Awaitable[AnyContext | AnyState | None] | AnyContext | AnyState | None:
        """Create the actor and return it. This method will create the actor and
        return it.
        """
        ...

    @property
    def __name__(self) -> str:
        """Get the name of the function. This method will return the name of the
        function.
        """
        ...


@runtime_checkable
class AsyncStartupFunction(Protocol):
    """A function that takes a passport and a transport and returns an actor.
    This method will create the actor and return it.
    """

    def __call__(self, instance_id: str) -> Awaitable[AnyContext | AnyState | None]:
        """Create the actor and return it. This method will create the actor and
        return it.
        """
        ...

    @property
    def __name__(self) -> str:
        """Get the name of the function. This method will return the name of the
        function.
        """
        ...


@runtime_checkable
class ThreadedStartupFunction(Protocol):
    """A function that takes a passport and a transport and returns an actor.
    This method will create the actor and return it.
    """

    def __call__(self, instance_id: str) -> AnyContext | AnyState | None:
        """Create the actor and return it. This method will create the actor and
        return it.
        """
        ...

    @property
    def __name__(self) -> str:
        """Get the name of the function. This method will return the name of the
        function.
        """
        ...
