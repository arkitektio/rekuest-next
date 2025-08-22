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

    def call(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        """Call the action with the given arguments.

        Returns:
            Any: The result of the action.
        """
        from rekuest_next.remote import call

        return call(self, *args, **kwargs)  # type: ignore

    async def acall(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        """Call the action with the given arguments asynchronously.

        Returns:
            Any: The result of the action.
        """
        from rekuest_next.remote import acall

        return await acall(self, *args, **kwargs)  # type: ignore

    def __call__(self, *args: typing.Any, **kwargs: typing.Any):
        """Call the action with the given arguments."""
        return self.call(*args, **kwargs)
