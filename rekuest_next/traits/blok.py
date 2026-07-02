from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel, model_validator

if TYPE_CHECKING:
    from rekuest_next.api.schema import CreateBlokInput, BlokImplementationInput


def _validate_demo_state_against_dependencies(
    dependencies: Iterable[Any] | None,
    demo_state: Mapping[str, Any] | None,
) -> None:
    if demo_state is None:
        return

    for dep in dependencies or ():
        dep_key = dep.key
        if dep_key not in demo_state:
            continue

        demo = demo_state[dep_key]
        state_keys = {state_demand.key for state_demand in dep.state_dependencies or ()}

        for state_key in state_keys:
            if state_key not in demo:
                raise ValueError(
                    f"demo_state for '{dep_key}' missing key '{state_key}' referenced in blok"
                )

        extra_keys = set(demo.keys()) - state_keys
        if extra_keys:
            raise ValueError(
                f"demo_state for '{dep_key}' has extra keys not referenced in blok: {sorted(extra_keys)}"
            )


class CreateBlokInputTrait(BaseModel):
    """
    Class for validating widget input
    on the client side

    """

    @model_validator(mode="after")  # type: ignore[override]
    def validate_widgetkind_nested(self: "CreateBlokInput") -> "CreateBlokInput":
        """Validate blok components against the provided dependencies."""
        from rekuest_next.blok.parser import validate_blok

        for component in self.components or ():
            validate_blok(component, list(self.dependencies or ()))

        demo_state = cast(
            dict[str, Any] | None,
            self.demo_state if isinstance(self.demo_state, dict) else None,
        )
        _validate_demo_state_against_dependencies(self.dependencies, demo_state)

        return self


class BlokImplementationInputTrait(BaseModel):
    """
    Class for validating widget input
    on the client side

    """

    @model_validator(mode="after")  # type: ignore[override]
    def validate_widgetkind_nested(
        self: "BlokImplementationInput",
    ) -> "BlokImplementationInput":
        """Validate blok components against the provided dependencies."""
        from rekuest_next.blok.parser import validate_blok

        for component in self.components or ():
            validate_blok(component, list(self.dependencies or ()))

        demo_state = cast(
            dict[str, Any] | None,
            self.demo_state if isinstance(self.demo_state, dict) else None,
        )
        _validate_demo_state_against_dependencies(self.dependencies, demo_state)

        return self
