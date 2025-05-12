"""Traits for actions , so that we can use them as reservable context"""

from koil.composition.base import KoiledModel


class Reserve(KoiledModel):
    """A class to reserve a action in the graph."""

    def get_action_kind(self) -> str:
        """Get the kind of the action.
        Returns:
            str: The kind of the action.
        """
        return getattr(self, "kind")
