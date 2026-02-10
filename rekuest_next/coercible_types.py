from typing import Protocol
from rekuest_next.api.schema import (
    ActionDependencyInput,
    AgentDependencyInput,
    OptimisticInput,
)


class ToDependencyProtocol(Protocol):
    """A type that can be coerced into a DependencyInput."""

    def to_dependency_input(self) -> AgentDependencyInput: ...


DependencyCoercible = AgentDependencyInput | ToDependencyProtocol


class ToOptimisticProtocol(Protocol):
    """A type that can be coerced into an OptimisticInput."""

    def to_optimistic_input(self) -> OptimisticInput: ...


OptimisticCoercible = OptimisticInput | ToOptimisticProtocol
