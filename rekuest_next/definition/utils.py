import logging
from rekuest_next.agents.context import is_context
from rekuest_next.api.schema import AssignWidgetInput, EffectInput, ReturnWidgetInput, ValidatorInput
from rekuest_next.definition.errors import DefinitionError
from rekuest_next.state.predicate import is_state

parsers = []

try:
    from annotated_types import Predicate, Le, Gt, Len
    
    def extract_annotated_types(annotations, assign_widget, return_widget, validators, effects, default, label, description):
        
        for annotation in annotations:
            if isinstance(annotation, Gt):
                validators.append(
                    ValidatorInput(
                        function=f"(x) => x > {annotation.gt}",
                        label=f"Must be greater than {annotation.gt}",
                        errorMessage=f"Must be greater than {annotation.gt}",
                    )
                )
            if isinstance(annotation, Len):
                validators.append(
                    ValidatorInput(
                        function=f"(x) => x.length > {annotation.max_length} && x.length < {annotation.min_length}",
                        label=f"Must have length inbetween {annotation.max_length} and {annotation.min_length}",
                        errorMessage=f"Must have length inbetween {annotation.max_length} and {annotation.min_length}",
                    )
                )
                
            
        return assign_widget, return_widget, validators, effects, default, label, description

    parsers.append(
        extract_annotated_types
    )

except ImportError:
    pass



def is_local_var(type):
    return is_context(type) or is_state(type)



def extract_basic_annotations(annotations, assign_widget, return_widget, validators, effects, default, label, description):

    str_annotation_count = 0
    
    for annotation in annotations:
        if isinstance(annotation, AssignWidgetInput):
            if assign_widget:
                raise DefinitionError(
                    "Multiple AssignWidgets found"
                )
            assign_widget = annotation
        elif isinstance(annotation, ReturnWidgetInput):
            if return_widget:
                raise DefinitionError(
                    "Multiple ReturnWidgets found"
                )
            return_widget = annotation
        elif isinstance(annotation, ValidatorInput):
            validators.append(annotation)
        elif isinstance(annotation, EffectInput):
            effects.append(annotation)
        
        elif hasattr(annotation, "get_assign_widget"):
            if assign_widget:
                raise DefinitionError(
                    "Multiple AssignWidgets found"
                )
            assign_widget = annotation.get_assign_widget()
        elif hasattr(annotation, "get_return_widget"):
            if return_widget:
                raise DefinitionError(
                    "Multiple ReturnWidgets found"
                )
            return_widget = annotation.get_return_widget()
        elif hasattr(annotation, "get_effects"):
            effects += annotation.get_effects()
        elif hasattr(annotation, "get_default"):
            if default:
                raise DefinitionError(
                    "Multiple Defaults found"
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


parsers.append(
    extract_basic_annotations
)


def extract_annotations(annotations, assign_widget, return_widget, validators, effects, default, label, description):
    
    
    for parser in parsers:
       
        assign_widget, return_widget, validators, effects, default, label, description = parser(
            annotations,
            assign_widget,
            return_widget,
            validators,
            effects,
            default,
            label,
            description
        )
        
    return assign_widget, return_widget, validators, effects, default, label, description