"""Traits for nodes , so that we can use them as reservable context"""

from typing import Dict, Any
from koil.composition.base import KoiledModel


class Reserve(KoiledModel):
    """A class to reserve a node in the graph."""

    def validate_args(self, **kwargs: Dict[str, Any]) -> None:
        """Validate the args of the node.
        Args:
            kwargs (dict): The args to validate.
        """
        for arg in self.args:
            if arg.key not in kwargs and arg.nullable is False:
                raise ValueError(f"Key {arg.key} not in args")

    def get_node_kind(self) -> str:
        """Get the kind of the node.
        Returns:
            str: The kind of the node.
        """
        return getattr(self, "kind")
