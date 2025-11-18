"""Traits for actions , so that we can use them as reservable context"""

from koil.composition.base import KoiledModel
import typing


class Callable(KoiledModel):
    """A class to reserve a action in the graph."""

    def get_action_kind(self) -> str:
        """Get the kind of the action.
        Returns:
            str: The kind of the action.
        """
        return getattr(self, "kind")

    def iterate(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Iterator[typing.Any]:
        """Iterate over the action with the given arguments.

        Returns:
            AsyncIterator[Any]: The result of the action.
        """
        from rekuest_next.remote import iterate
        from rekuest_next.api.schema import ActionKind

        assert self.get_action_kind() == ActionKind.GENERATOR, (
            "Action kind must be GENERATOR to use iterate."
        )

        return iterate(self, *args, **kwargs)  # type: ignore

    def call(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        """Call the action with the given arguments.

        Returns:
            Any: The result of the action.
        """
        from rekuest_next.remote import call
        from rekuest_next.api.schema import ActionKind

        assert self.get_action_kind() == ActionKind.FUNCTION, (
            "Action kind must be FUNCTION to use call."
        )

        return call(self, *args, **kwargs)  # type: ignore

    async def aiterate(
        self, *args: typing.Any, **kwargs: typing.Any
    ) -> typing.AsyncIterator[typing.Any]:
        """Asynchronously iterate over the action with the given arguments.

        Returns:
            AsyncIterator[Any]: The result of the action.
        """
        from rekuest_next.remote import aiterate
        from rekuest_next.api.schema import ActionKind

        assert self.get_action_kind() == ActionKind.GENERATOR, (
            "Action kind must be GENERATOR to use aiterate."
        )

        return aiterate(self, *args, **kwargs)  # type: ignore

    async def acall(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        """Call the action with the given arguments asynchronously.

        Returns:
            Any: The result of the action.
        """
        from rekuest_next.remote import acall
        from rekuest_next.api.schema import ActionKind

        assert self.get_action_kind() == ActionKind.FUNCTION, (
            "Action kind must be FUNCTION to use acall."
        )

        return await acall(self, *args, **kwargs)  # type: ignore

    def __call__(self, *args: typing.Any, **kwargs: typing.Any):
        """Call the action with the given arguments."""

        from rekuest_next.api.schema import ActionKind

        if self.get_action_kind() == ActionKind.GENERATOR:
            return self.iterate(*args, **kwargs)

        return self.call(*args, **kwargs)
