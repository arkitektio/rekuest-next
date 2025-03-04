from typing import Callable
from pydantic import BaseModel, field_validator, model_validator
import uuid
import random
import re

class PortTrait(BaseModel):
    """
    Class for validating port input
    on the client side

    """

    @field_validator("default", check_fields=False)
    def validator(cls, v, info):
        # Check if the default value is JSON serializable
        if v is None:
            return v

        if not isinstance(v, (str, int, float, dict, list, bool)):
            raise ValueError(
                "Default value must be JSON serializable, got: " + str(v)
            ) from None

        return v

    @model_validator(mode="after")
    def validate_portkind_nested(cls, self):
        from rekuest_next.api.schema import PortKind

        if self.kind == PortKind.STRUCTURE:
            if self.identifier is None:
                raise ValueError(
                    "When specifying a structure you need to provide an arkitekt"
                    " identifier got:"
                )

        if self.kind == PortKind.LIST:
            if self.children is None:
                raise ValueError(
                    "When specifying a list you need to provide a wrapped 'children' port"
                )
            assert len(self.children) == 1, "List can only have one child"

        if self.kind == PortKind.DICT:
            if self.children is None:
                raise ValueError(
                    "When specifying a dict you need to provide a wrapped 'children' port"
                )
            assert (
                len(self.children) == 1
            ), "Dict can only one child (key is always strings)"

        return self

    def mock(
        self,
        structure_generator: Callable = uuid.uuid4,
        int_generator: Callable = lambda: random.randint(0, 100),
        float_generator: Callable = lambda: random.random(),
        string_generator: Callable = lambda: str("sss"),
    ):
        """
        Mocks some serialized data for this port
        """
        from rekuest_next.api.schema import PortKind

        kind = self.kind

        if kind == PortKind.STRUCTURE:
            return str(structure_generator())

        if kind == PortKind.LIST:
            return [self.child.mock()]

        if kind == PortKind.DICT:
            return {"hello": self.child.mock(), "world": self.child.mock()}

        if kind == PortKind.STRING:
            return string_generator()

        if kind == PortKind.INT:
            return int_generator()

        if kind == PortKind.BOOL:
            return float_generator()

        return None


class WidgetInputTrait(BaseModel):
    """
    Class for validating widget input
    on the client side

    """

    @model_validator(mode="after")
    def validate_widgetkind_nested(cls, self):
        from rekuest_next.api.schema import AssignWidgetKind

        if self.kind == AssignWidgetKind.SEARCH:
            if self.query is None:
                raise ValueError(
                    "When specifying a SearchWidget you need to provide an query"
                    " parameter"
                )

        if self.kind == AssignWidgetKind.SLIDER:
            if self.min is None or self.max is None:
                raise ValueError(
                    "When specifying a Slider you need to provide an 'max and 'min'"
                    " parameter"
                )

            if self.min > self.max:
                raise ValueError(
                    "When specifying a Slider you need to provide an 'max' greater than"
                    " 'min'"
                )

        return self


class ReturnWidgetInputTrait(BaseModel):
    """
    Class for validating widget input
    on the client side

    """

    @model_validator(mode="after")
    def validate_widgetkind_nested(cls, self):
        from rekuest_next.api.schema import ReturnWidgetKind

        if self.kind is None:
            raise ValueError("kind is required")

        if self.kind == ReturnWidgetKind.CUSTOM:
            if self.hook is None:
                raise ValueError(
                    "When specifying a CustomReturnWidget you need to provide a 'hook'"
                    " parameter, corresponding to the desired reigstered hook"
                )

        return self




class ValidatorInputTrait(BaseModel):
    
    @model_validator(mode="after")
    def validate_widgetkind_nested(cls, self):
        from rekuest_next.api.schema import ReturnWidgetKind
        
        
        
        args_match = re.match(r'\((.*?)\)', self.function)
        if args_match:
            args = [arg.strip() for arg in args_match.group(1).split(',') if arg.strip()]
            if not args:
                raise ValueError("Function must have at least one argument")

            if len(args) - 1 is not len(self.dependencies):
                raise ValueError( f"The number of arguments in the function must match the number of dependencies, plus one for the input value. Found {len(args)} arguments and {len(self.dependencies)} dependencies")
        else:
            raise ValueError("Function must have at least one argument")

        return self
    
    
    
    
class DefinitionInputTrait(BaseModel):
    
    
    
    @model_validator(mode="after")
    def validate_validators(cls, self):
        
        all_arg_keys = []
    
        
        for port in self.args:
            all_arg_keys.append(port.key)
            
            
        for port in self.args:
            if port.validators:
                for validator in port.validators:
                    for dep in validator.dependencies:
                        if dep not in all_arg_keys:
                            raise ValueError(f"Dependency '{dep}' for '{validator.function}' at port '{port.key} not found in args. Please make sure the dependency is in the args")
                        
                        
                        
        return self
        
        