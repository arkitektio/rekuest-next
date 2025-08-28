from typing import Protocol
from rekuest_next.api.schema import ActionDependencyInput


class ToDependencyProtocol(Protocol):
    """A type that can be coerced into a DependencyInput."""

    def to_dependency_input(self) -> ActionDependencyInput: ...


DependencyCoercible = ActionDependencyInput | ToDependencyProtocol
