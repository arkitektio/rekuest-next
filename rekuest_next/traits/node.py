"""Traits for actions , so that we can use them as reservable context"""

from typing import Dict, Any
from koil.composition.base import KoiledModel


class Reserve(KoiledModel):
    """A class to reserve a action in the graph."""

    def validate_args(self, **kwargs: Dict[str, Any]) -> None:
        """Validate the args of the action.
        Args:
            kwargs (dict): The args to validate.
        """
        for arg in self.args:
            if arg.key not in kwargs and arg.nullable is False:
                raise ValueError(f"Key {arg.key} not in args")

    def get_action_kind(self) -> str:
        """Get the kind of the action.
        Returns:
            str: The kind of the action.
        """
        return getattr(self, "kind")
