from typing import Callable
from pydantic import BaseModel, root_validator, validator
import uuid
import random


class PortTrait(BaseModel):
    """
    Class for validating port input
    on the client side

    """

    @validator("default", check_fields=False)
    def validator(cls, v):
        # Check if the default value is JSON serializable
        if v is None:
            return v

        if not isinstance(v, (str, int, float, dict, list, bool)):
            raise ValueError(
                "Default value must be JSON serializable, got: " + str(v)
            ) from None

        return v

    @root_validator(pre=True)
    def validate_portkind_nested(cls, values):
        from rekuest.api.schema import PortKind

        kind = values.get("kind")

        if kind is None:
            raise ValueError("kind is required")

        if kind == PortKind.STRUCTURE:
            if values.get("identifier") is None:
                raise ValueError(
                    "When specifying a structure you need to provide an arkitekt"
                    " identifier got:" + str(values)
                )

        if kind == PortKind.LIST:
            if values.get("child") is None:
                raise ValueError(
                    "When specifying a list you need to provide a wrapped 'child' port"
                )

        return values

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
        from rekuest.api.schema import PortKind

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

    @root_validator(pre=True)
    def validate_widgetkind_nested(cls, values):
        from rekuest.api.schema import WidgetKind

        kind = values.get("kind")

        if kind is None:
            raise ValueError("kind is required")

        if kind == WidgetKind.SearchWidget:
            if values.get("query") is None:
                raise ValueError(
                    "When specifying a SearchWidget you need to provide an query"
                    " parameter"
                )

        if kind == WidgetKind.SliderWidget:
            if values.get("min") is None or values.get("max") is None:
                raise ValueError(
                    "When specifying a Slider you need to provide an 'max and 'min'"
                    f" parameter {values}"
                )

            if values.get("min") > values.get("max"):
                raise ValueError(
                    "When specifying a Slider you need to provide an 'max' greater than"
                    " 'min'"
                )

        return values


class ReturnWidgetInputTrait(BaseModel):
    """
    Class for validating widget input
    on the client side

    """

    @root_validator(pre=True)
    def validate_widgetkind_nested(cls, values):
        from rekuest.api.schema import ReturnWidgetKind

        kind = values.get("kind")

        if kind is None:
            raise ValueError("kind is required")

        if kind == ReturnWidgetKind.CustomReturnWidget:
            if values.get("hook") is None:
                raise ValueError(
                    "When specifying a CustomReturnWidget you need to provide a 'hook'"
                    " parameter, corresponding to the desired reigstered hook"
                )

        return values


class AnnotationInputTrait(BaseModel):
    """
    Abstract class for serialization of data.

    """

    @root_validator(pre=True)
    def validate_annotationkind_nested(cls, values):
        from rekuest.api.schema import AnnotationKind

        kind = values.get("kind")

        if kind is None:
            raise ValueError("kind is required")

        if kind == AnnotationKind.ValueRange:
            if values.get("min") is None and values.get("max") is None:
                raise ValueError("min or max is required when using Value Range")

            if values.get("min") is not None and values.get("max") is not None:
                if values.get("min") > values.get("max"):
                    raise ValueError(
                        "When using a ValueRange min must be less than max"
                    )

        if kind == AnnotationKind.IsPredicate:
            if values.get("predicate") is None:
                raise ValueError("predicate is required when using IsPredicate")

        if kind == AnnotationKind.CustomAnnotation:
            if values.get("hook") is None:
                raise ValueError("hook is required when using CustomAnnotation")

        if kind == AnnotationKind.AttributePredicate:
            if values.get("attribute") is None:
                raise ValueError("atrribute is required when using AttributePredicate")
            if values.get("annotations") is None:
                raise ValueError(
                    "annotations on the predicate is required when using"
                    " AttributePredicate"
                )

        return values
