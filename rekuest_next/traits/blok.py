from typing import TYPE_CHECKING

from pydantic import BaseModel, model_validator

if TYPE_CHECKING:
    from rekuest_next.api.schema import CreateBlokInput, BlokImplementationInput


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

        # Validate demo_state against referenced state schemas
        if self.demo_state:
            for dep in self.dependencies or ():
                dep_key = dep.key
                if dep_key in self.demo_state:
                    demo = self.demo_state[dep_key]
                    # Find all referenced state keys for this dependency
                    state_keys = set()
                    for state_demand in dep.state_demands or ():
                        state_keys.add(state_demand.key)
                    for state_key in state_keys:
                        if state_key not in demo:
                            raise ValueError(
                                f"demo_state for '{dep_key}' missing key '{state_key}' referenced in blok"
                            )
                    # Check for extra keys
                    extra_keys = set(demo.keys()) - state_keys
                    if extra_keys:
                        raise ValueError(
                            f"demo_state for '{dep_key}' has extra keys not referenced in blok: {sorted(extra_keys)}"
                        )

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

        # Validate demo_state against referenced state schemas
        if self.demo_state:
            for dep in self.dependencies or ():
                dep_key = dep.key
                if dep_key in self.demo_state:
                    demo = self.demo_state[dep_key]
                    # Find all referenced state keys for this dependency
                    state_keys = set()
                    for state_demand in dep.state_demands or ():
                        state_keys.add(state_demand.key)
                    for state_key in state_keys:
                        if state_key not in demo:
                            raise ValueError(
                                f"demo_state for '{dep_key}' missing key '{state_key}' referenced in blok"
                            )
                    # Check for extra keys
                    extra_keys = set(demo.keys()) - state_keys
                    if extra_keys:
                        raise ValueError(
                            f"demo_state for '{dep_key}' has extra keys not referenced in blok: {sorted(extra_keys)}"
                        )

        return self
