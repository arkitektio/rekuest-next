from typing import Any, Awaitable, Protocol, runtime_checkable


@runtime_checkable
class AnyFunction(Protocol):
    """A function that takes a passport and a transport and returns an actor.
    This method will create the actor and return it.
    """

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
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
class AnyContext(Protocol):
    """A function that takes a passport and a transport and returns an actor.
    This method will create the actor and return it.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
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
class StartupFunction(Protocol):
    """A function that takes a passport and a transport and returns an actor.
    This method will create the actor and return it.
    """

    def __call__(
        self, *args: Any, **kwargs: Any
    ) -> Awaitable[AnyContext | AnyState | None]:
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
