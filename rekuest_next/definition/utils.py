import logging
from rekuest_next.agents.context import is_context
from rekuest_next.api.schema import AssignWidgetInput, EffectInput, ReturnWidgetInput, ValidatorInput
from rekuest_next.definition.errors import DefinitionError
from rekuest_next.state.predicate import is_state


try:
    from typing import Annotated, get_type_hints, Any, get_origin

    annot_type = type(Annotated[int, "spam"])

    def is_annotated(obj: Any) -> bool:
        """Checks if a hint is an Annotated type

        Args:
            hint (Any): The typehint to check
            annot_type (_type_, optional): _description_. Defaults to annot_type.

        Returns:
            bool: _description_
        """
        return get_origin(obj) is Annotated

except ImportError:
    Annotated = None
    from typing import get_type_hints as _get_type_hints, Any

    def get_type_hints(obj: Any, include_extras=False, **kwargs):
        return _get_type_hints(obj, **kwargs)

    def is_annotated(obj: Any) -> bool:
        """Checks if a hint is an Annotated type

        Args:
            hint (Any): The typehint to check
            annot_type (_type_, optional): _description_. Defaults to annot_type.

        Returns:
            bool: _description_
        """
        return False


def is_local_var(type):
    return is_context(type) or is_state(type)



def extract_annotations(annotations, assign_widget, return_widget, validators, effects, default, label, description):

    str_annotation_count = 0
    
    for annotation in annotations:
        if isinstance(annotation, AssignWidgetInput):
            if assign_widget:
                raise DefinitionError(
                    f"Multiple AssignWidgets found"
                )
            assign_widget = annotation
        elif isinstance(annotation, ReturnWidgetInput):
            if return_widget:
                raise DefinitionError(
                    f"Multiple ReturnWidgets found"
                )
            return_widget = annotation
        elif isinstance(annotation, ValidatorInput):
            validators.append(annotation)
        elif isinstance(annotation, EffectInput):
            effects.append(annotation)
        
        elif hasattr(annotation, "get_assign_widget"):
            if assign_widget:
                raise DefinitionError(
                    f"Multiple AssignWidgets found"
                )
            assign_widget = annotation.get_assign_widget()
        elif hasattr(annotation, "get_return_widget"):
            if return_widget:
                raise DefinitionError(
                    f"Multiple ReturnWidgets found"
                )
            return_widget = annotation.get_return_widget()
        elif hasattr(annotation, "get_effects"):
            effects += annotation.get_effects()
        elif hasattr(annotation, "get_default"):
            if default:
                raise DefinitionError(
                    f"Multiple Defaults found"
                )
            
            default = annotation.get_default()
        elif hasattr(annotation, "get_validators"):
            validators += annotation.get_validators()
        elif isinstance(annotation, str):
            if str_annotation_count > 0:
                description = annotation
            else:
                label = annotation
                
            str_annotation_count += 1
            
            
        else:
            logging.warning(f"Unrecognized annotation {annotation}")
            
            
    return assign_widget, return_widget, validators, effects, default, label, description