from enum import Enum
from typing import Callable, List, Tuple, Type, Union

from rekuest_next.structures.model import (
    is_model,
    retrieve_fullfiled_model,
)
from rekuest_next.structures.serialization.predication import predicate_port
from .utils import extract_annotations, get_type_hints, is_annotated, is_local_var
from rekuest_next.api.schema import (
    PortInput,
    ChildPortInput,
    DefinitionInput,
    NodeKind,
    PortKind,
    PortScope,
    AssignWidgetInput,
    ReturnWidgetInput,
    PortGroupInput,
    EffectInput,
    ValidatorInput,
)
import inspect
from docstring_parser import parse
from rekuest_next.definition.errors import DefinitionError, NonSufficientDocumentation
import datetime as dt
from rekuest_next.structures.registry import (
    StructureRegistry,
)
from typing import (
    Optional,
    Any,
    Dict,
    get_origin,
    get_args,
    Annotated
)
import types
import typing

def is_union_type(cls):
    # We are dealing with a 3.10 Union (PEP 646)
    try:
        return get_origin(cls) is types.UnionType 
    except AttributeError:
        return False



def is_nullable(cls):
    is_union = is_union_type(cls) or get_origin(cls) is Union

    if is_union:
        for arg in get_args(cls):
            if arg == type(None):
                return True

    return False


def get_non_nullable_variant(cls):
    non_nullable_args = [arg for arg in get_args(cls) if arg != type(None)]
    if len(non_nullable_args) == 1:
        return non_nullable_args[0]
    # We are dealing with a Union so we still use the same class
    # the logic will be handled in the union path
    # TODO: We might want to handle this better
    return cls


def is_union(cls):
    return (
        is_union_type(cls)
        or get_origin(cls) is Union
        and get_args(cls)[1] != type(None)
    )


def is_tuple(cls):
    return get_origin(cls) in (tuple, typing.Tuple)


def is_list(cls):
    """Check if a class is a list



    if cls.__module__ == "typing":
        if hasattr(cls, "_name"):
            # We are dealing with a Typing Var?
            if cls._name == "List":

    Returns:
        _type_: _description_
    """
    return get_origin(cls) == list


def is_dict(cls):
    """Check if a class is a dict

    if cls.__module__ == "typing":
        if hasattr(cls, "_name"):
            if cls._name == "Dict":

    Returns:
        _type_: _description_
    """
    return get_origin(cls) == dict


def get_dict_value_cls(cls):
    return get_args(cls)[1]


def get_list_value_cls(cls):
    return get_args(cls)[0]


def get_non_null_variants(cls):
    return [arg for arg in get_args(cls) if arg != type(None)]


def is_bool(cls, default=None):
    if inspect.isclass(cls):
        return not issubclass(cls, Enum) and issubclass(cls, bool)
    return False


def is_float(cls):
    if inspect.isclass(cls):
        return not issubclass(cls, Enum) and issubclass(cls, float)
    return False


def is_generator_type(cls):
    if cls.__module__ == "typing":
        if hasattr(cls, "_name"):
            if cls._name == "Generator":
                return True
            if cls._name == "AsyncGenerator":
                return True
    return False


def is_int(cls):
    if inspect.isclass(cls):
        return not issubclass(cls, Enum) and issubclass(cls, int)
    return False


def is_str(cls):
    if inspect.isclass(cls):
        return not issubclass(cls, Enum) and issubclass(cls, str)
    return False


def is_datetime(cls):
    if inspect.isclass(cls):
        return not issubclass(cls, Enum) and (issubclass(cls, dt.datetime))
    return False


def is_structure(cls):
    return True


def convert_child_to_childport(
    cls: Type,
    registry: StructureRegistry,
    nullable: bool = False,
    key: Optional[str] = None,
    description: Optional[str] = None,
    assign_widget: Optional[AssignWidgetInput] = None,
    return_widget: Optional[ReturnWidgetInput] = None,
) -> Tuple[ChildPortInput, Callable]:
    """Converts a element of a annotation to a child port

    Args:
        cls (Type): The type (class or annotation) of the elemtn
        registry (StructureRegistry): The structure registry to use
        nullable (bool, optional): Is this type optional (recursive parameter).
            Defaults to False.
        is_return (bool, optional): Is this a return type?. Defaults to False.
        annotations (List[AnnotationInput], optional): The annotations for this element.
            Defaults to None.

    Returns:
        Tuple[ChildPortInput, WidgetInput, Callable]: The child port, the widget and the
         converter for the default
    """
    if is_model(cls):
        children = []
        convertermap = {}

        full_filled_model = retrieve_fullfiled_model(cls)

        registry.register_as_model(cls, full_filled_model.identifier)

        for arg in full_filled_model.args:
            child, converter = convert_child_to_childport(
                arg.cls,
                registry,
                nullable=False,
                key=arg.key,
                description=arg.description,
            )
            children.append(child)
            convertermap[arg.key] = converter

        return (
            ChildPortInput(
                kind=PortKind.MODEL,
                children=children,
                scope=PortScope.GLOBAL,
                identifier=full_filled_model.identifier,
                nullable=nullable,
                key=key,
                description=full_filled_model.description,
            ),
            lambda default: default.model_dump(),
        )

    if is_annotated(cls):
        real_type, *args = get_args(cls)

        for annotation in args:
            if hasattr(annotation, "get_assign_widget"):
                assign_widget = annotation.get_assign_widget()
            if hasattr(annotation, "get_return_widget"):
                return_widget = annotation.get_return_widget()

        return convert_child_to_childport(
            real_type,
            registry,
            nullable=nullable,
            key=key,
            assign_widget=assign_widget,
            return_widget=return_widget,
        )

    if is_nullable(cls):
        non_nullable = get_non_nullable_variant(cls)
        return convert_child_to_childport(
            non_nullable,
            registry,
            nullable=True,
            key=key,
            assign_widget=assign_widget,
            return_widget=return_widget,
        )

    if is_union(cls):
        variants = get_non_null_variants(cls)
        children = []
        converters = []
        for index, arg in enumerate(variants):
            child, converter = convert_child_to_childport(
                arg, registry, nullable=False, key="variant_" + str(index)
            )
            converters.append(converter)
            children.append(child)

        return ChildPortInput(
            kind=PortKind.UNION,
            scope=PortScope.GLOBAL,
            key=key,
            children=children,
            nullable=nullable,
            description=description,
        )

    if is_list(cls):
        value_cls = get_list_value_cls(cls)
        child, nested_converter = convert_child_to_childport(
            value_cls, registry, nullable=False, key="..."
        )

        return (
            ChildPortInput(
                kind=PortKind.LIST,
                children=[child],
                scope=PortScope.GLOBAL,
                nullable=nullable,
                key=key,
                description=description,
            ),
            lambda default: (
                [nested_converter(ndefault) for ndefault in default]
                if default
                else None
            ),
        )

    if is_dict(cls):
        value_cls = get_dict_value_cls(cls)
        child, nested_converter = convert_child_to_childport(
            value_cls, registry, nullable=False, key="..."
        )
        return (
            ChildPortInput(
                kind=PortKind.DICT,
                children=[child],
                scope=PortScope.GLOBAL,
                nullable=nullable,
                key=key,
                description=description,
            ),
            lambda default: (
                {key: item in nested_converter(item) for key, item in default.items()}
                if default
                else None
            ),
        )

    if is_bool(cls):
        return (
            ChildPortInput(
                kind=PortKind.BOOL,
                nullable=nullable,
                scope=PortScope.GLOBAL,
                key=key,
                description=description,
            ),
            bool,
        )

    if is_float(cls):
        return (
            ChildPortInput(
                kind=PortKind.FLOAT,
                nullable=nullable,
                scope=PortScope.GLOBAL,
                key=key,
                description=description,
            ),
            float,
        )

    if is_int(cls):
        return (
            ChildPortInput(
                kind=PortKind.INT,
                nullable=nullable,
                scope=PortScope.GLOBAL,
                key=key,
                description=description,
            ),
            int,
        )

    if is_datetime(cls):
        return (
            ChildPortInput(
                kind=PortKind.DATE,
                nullable=nullable,
                scope=PortScope.GLOBAL,
                key=key,
                description=description,
            ),
            lambda x: x.isoformat(),
        )

    if is_str(cls):
        return (
            ChildPortInput(
                kind=PortKind.STRING,
                nullable=nullable,
                scope=PortScope.GLOBAL,
                key=key,
                description=description,
            ),
            str,
        )

    if is_structure(cls):
        return registry.get_child_port_and_default_converter_for_cls(
            cls,
            nullable=nullable,
            key=key,
            description=description,
        )

    raise NotImplementedError(f"Could not convert {cls} to a child port")


def convert_object_to_port(
    cls,
    key,
    registry: StructureRegistry,
    assign_widget=None,
    return_widget=None,
    default=None,
    label=None,
    description=None,
    nullable=False,
    validators: Optional[List[ValidatorInput]] = None,
    effects: Optional[List[EffectInput]] = None,
) -> PortInput:
    """
    Convert a class to an Port
    """

    if is_generator_type(cls):
        real_type = cls.__args__[0]

        return convert_object_to_port(
            real_type,
            key,
            registry,
            assign_widget=assign_widget,
            default=default,
            label=label,
            effects=effects,
            nullable=nullable,
        )

    if is_model(cls):
        children = []
        converters = []
        set_default = default or {}

        full_filled_model = retrieve_fullfiled_model(cls)

        registry.register_as_model(cls, full_filled_model.identifier)

        for arg in full_filled_model.args:
            child, converter = convert_child_to_childport(
                arg.cls,
                registry,
                nullable=False,
                key=arg.key,
                description=arg.description,
            )
            children.append(child)
            if arg.default:
                set_default[arg.key] = converter(arg.default)

        return PortInput(
            kind=PortKind.MODEL,
            assignWidget=assign_widget,
            returnWidget=return_widget,
            scope=PortScope.GLOBAL,
            key=key,
            children=children,
            label=label,
            default=set_default,
            nullable=nullable,
            effects=effects ,
            description=description or full_filled_model.description,
            validators=validators,
            identifier=full_filled_model.identifier,
        )

    if is_annotated(cls):
        real_type, *annotations = get_args(cls)
        
        
        assign_widget, return_widget, validators, effects, default, label, description = extract_annotations(
            annotations, assign_widget, return_widget, validators, effects, default, label, description
        )

        

        return convert_object_to_port(
            real_type,
            key,
            registry,
            assign_widget=assign_widget,
            default=default,
            label=label,
            effects=effects,
            nullable=nullable,
            validators=validators,
            description=description,
        )

    if is_list(cls):
        value_cls = get_list_value_cls(cls)
        child, converter = convert_child_to_childport(
            value_cls, registry, nullable=False, key="..."
        )
        return PortInput(
            kind=PortKind.LIST,
            assignWidget=assign_widget,
            returnWidget=return_widget,
            scope=PortScope.GLOBAL,
            key=key,
            children=[child],
            label=label,
            default=[converter(item) for item in default] if default else None,
            nullable=nullable,
            effects=effects,
            description=description,
            validators=validators,
        )

    if is_nullable(cls):
        return convert_object_to_port(
            cls.__args__[0],
            key,
            registry,
            default=default,
            nullable=True,
            assign_widget=assign_widget,
            label=label,
            effects=effects,
            return_widget=return_widget,
            description=description,
            validators=validators,
        )

    if is_union(cls):
        variants = get_non_null_variants(cls)
        children = []
        converters = []
        for index, arg in enumerate(variants):
            child, converter = convert_child_to_childport(
                arg, registry, nullable=False, key="variant_" + str(index)
            )
            converters.append(converter)
            children.append(child)

        set_default = None
        if default:
            # We need to find the correct converter according
            # to the default value (checking the predicate)
            for index, child in enumerate(children):
                if predicate_port(child, default, registry):
                    set_default = converters[index](default)
                    break

        return PortInput(
            kind=PortKind.UNION,
            assignWidget=assign_widget,
            returnWidget=return_widget,
            scope=PortScope.GLOBAL,
            key=key,
            children=children,
            label=label,
            default=set_default,
            nullable=nullable,
            effects=effects,
            validators=validators,
            description=description,
        )

    if is_dict(cls):
        value_cls = get_dict_value_cls(cls)
        child, converter = convert_child_to_childport(
            value_cls, registry, nullable=False, key="..."
        )
        return PortInput(
            kind=PortKind.DICT,
            assignWidget=assign_widget,
            scope=PortScope.GLOBAL,
            returnWidget=return_widget,
            key=key,
            children=[child],
            label=label,
            default=(
                {key: converter(item) for key, item in default.items()}
                if default
                else None
            ),
            nullable=nullable,
            effects=effects,
            validators=validators,
            description=description,
        )

    if is_bool(cls) or (default is not None and isinstance(default, bool)):
        return PortInput(
            kind=PortKind.BOOL,
            scope=PortScope.GLOBAL,
            assignWidget=assign_widget,
            returnWidget=return_widget,
            key=key,
            default=default,
            label=label,
            nullable=nullable,
            effects=effects,
            validators=validators,
            description=description,
        )  # catch bool is subclass of int

    if is_int(cls) or (default is not None and isinstance(default, int)):
        return PortInput(
            kind=PortKind.INT,
            assignWidget=assign_widget,
            scope=PortScope.GLOBAL,
            returnWidget=return_widget,
            key=key,
            default=default,
            label=label,
            nullable=nullable,
            effects=effects,
            validators=validators,
            description=description,
        )

    if is_float(cls) or (default is not None and isinstance(default, float)):
        return PortInput(
            kind=PortKind.FLOAT,
            assignWidget=assign_widget,
            returnWidget=return_widget,
            scope=PortScope.GLOBAL,
            key=key,
            default=default,
            label=label,
            nullable=nullable,
            validators=validators,
            effects=effects,
            description=description,
        )

    if is_datetime(cls) or (default is not None and isinstance(default, dt.datetime)):
        return PortInput(
            kind=PortKind.DATE,
            assignWidget=assign_widget,
            returnWidget=return_widget,
            scope=PortScope.GLOBAL,
            key=key,
            default=default,
            label=label,
            nullable=nullable,
            effects=effects,
            validators=validators,
            description=description,
        )

    if is_str(cls) or (default is not None and isinstance(default, str)):
        return PortInput(
            kind=PortKind.STRING,
            assignWidget=assign_widget,
            returnWidget=return_widget,
            scope=PortScope.GLOBAL,
            key=key,
            default=default,
            label=label,
            nullable=nullable,
            effects=effects,
            validators=validators,
            description=description,
        )

    if is_structure(cls):
        return registry.get_port_for_cls(
            cls,
            key,
            nullable=nullable,
            description=description,
            effects=effects,
            label=label,
            default=default,
            validators=validators,
            assign_widget=assign_widget,
            return_widget=return_widget,
        )

    raise NotImplementedError(f"Could not convert {cls} to a port")


GroupMap = Dict[str, List[str]]
AssignWidgetMap = Dict[str, List[AssignWidgetInput]]
ReturnWidgetMap = Dict[str, List[ReturnWidgetInput]]
EffectsMap = Dict[str, List[EffectInput]]


def snake_to_title_case(snake_str):
    # Split the string by underscores
    words = snake_str.split("_")

    # Capitalize each word
    capitalized_words = [word.capitalize() for word in words]

    # Join the words back into a single string with spaces in between
    title_case_str = " ".join(capitalized_words)

    return title_case_str


def prepare_definition(
    function: Callable,
    structure_registry: StructureRegistry,
    widgets: Optional[AssignWidgetMap] = None,
    return_widgets: Optional[ReturnWidgetMap] = None,
    effects: Optional[EffectsMap] = None,
    port_groups: List[PortGroupInput]  | None  = None,
    allow_empty_doc=True,
    collections: List[str] = [],
    interfaces: Optional[List[str]] = None,
    description: str | None = None,
    stateful: bool = False,
    is_test_for: Optional[List[str]] = None,
    port_label_map: Optional[Dict[str, str]] = None,
    port_description_map: Optional[Dict[str, str]] = None,
    validators: Optional[Dict[str, List[ValidatorInput]]] = None,
    name: str | None = None,
    omitfirst=None,
    omitlast=None,
    omitkeys=[],
    return_annotations: Optional[List[Any]] = None,
    allow_dev=True,
    allow_annotations: bool = True,
    **kwargs,  # additional kwargs can be ignored
) -> DefinitionInput:
    """Define

    Define a callable (async function, sync function, async generator, async
    generator) in the context of arkitekt and
    return its definition(input).

    Attention this definition is not yet registered in the
    arkitekt registry. This is done by the create_template function ( which will
    validate he definition with your local arkitekt instance
    and raise an error if the definition is not compatible with your arkitekt version)


    Args:
        function (): The function you want to define
    """

    assert structure_registry is not None, "You need to pass a StructureRegistry"

    is_generator = inspect.isasyncgenfunction(function) or inspect.isgeneratorfunction(
        function
    )

    sig = inspect.signature(function)
    widgets = widgets or {}
    effects = effects or {}
    validators = validators or {}

    port_groups = port_groups or []

    return_widgets = return_widgets or {}
    interfaces = interfaces or []
    collections = collections or []
    # Generate Args and Kwargs from the Annotation
    args: List[PortInput] = []
    returns: List[PortInput] = []

    # Docstring Parser to help with descriptions
    docstring = parse(function.__doc__)

    is_dev = False

    if not docstring.short_description and name is None:
        is_dev = True
        if not allow_dev:
            raise NonSufficientDocumentation(
                f"We are not in dev mode. Please provide a name or better document  {function.__name__}. Try docstring :)"
            )

    if not docstring.long_description and description is None and not allow_empty_doc:
        is_dev = True
        if not allow_dev:
            raise NonSufficientDocumentation(
                f"We are not in dev mode. Please provide a description or better document  {function.__name__}. Try docstring :)"
            )

    type_hints = get_type_hints(function, include_extras=allow_annotations)
    function_ins_annotation = sig.parameters

    doc_param_description_map = {
        param.arg_name: param.description for param in docstring.params
    }
    doc_param_label_map = {param.arg_name: param.arg_name for param in docstring.params}

    if docstring.many_returns:
        doc_param_description_map.update(
            {
                f"return{index}": param.description
                for index, param in enumerate(docstring.many_returns)
            }
        )
        doc_param_label_map.update(
            {
                f"return{index}": param.return_name
                for index, param in enumerate(docstring.many_returns)
            }
        )
    elif docstring.returns:
        doc_param_description_map.update({"return0": docstring.returns.description})
        doc_param_label_map.update({"return0": docstring.returns.return_name})

    if port_label_map:
        doc_param_label_map.update(port_label_map)
    if port_description_map:
        doc_param_description_map.update(port_description_map)

    for index, (key, value) in enumerate(function_ins_annotation.items()):
        # We can skip arguments if the builder is going to provide additional arguments
        if omitfirst is not None and index < omitfirst:
            continue
        if omitlast is not None and index > omitlast:
            continue
        if key in omitkeys:
            continue

        assign_widget = widgets.pop(key, None)
        port_effects = effects.pop(key, [])
        return_widget = return_widgets.pop(key, None)
        item_validators = validators.pop(key, [])
        default = value.default if value.default != inspect.Parameter.empty else None
        cls = type_hints.get(key, type(default) if default is not None else None)

        if cls is None:
            raise DefinitionError(
                f"Could not find type hint for {key} in {function.__name__}. Please provide a type hint (or default) for this argument."
            )

        if is_local_var(cls):
            continue

        try:
            args.append(
                convert_object_to_port(
                    cls,
                    key,
                    structure_registry,
                    assign_widget=assign_widget,
                    return_widget=return_widget,
                    default=default,
                    effects=port_effects,
                    nullable=value.default != inspect.Parameter.empty,
                    description=doc_param_description_map.pop(key, None),
                    label=doc_param_label_map.pop(key, None),
                    validators=item_validators,
                )
            )
        except Exception as e:
            raise DefinitionError(
                f"Could not convert Argument of function {function.__name__} to"
                f" ArgPort: {value}"
            ) from e

    function_outs_annotation = sig.return_annotation

    if return_annotations:
        for index, cls in enumerate(return_annotations):
            key = f"return{index}"
            return_widget = return_widgets.pop(key, None)
            assign_widget = widgets.pop(key, None)
            port_effects = effects.pop(key, None)

            returns.append(
                convert_object_to_port(
                    cls,
                    key,
                    structure_registry,
                    return_widget=return_widget,
                    effects=port_effects,
                    description=doc_param_description_map.pop(key, None),
                    label=doc_param_label_map.pop(key, None),
                    assign_widget=assign_widget,
                )
            )

    elif is_tuple(function_outs_annotation):
        for index, cls in enumerate(get_args(function_outs_annotation)):
            key = f"return{index}"
            return_widget = return_widgets.pop(key, None)
            assign_widget = widgets.pop(key, None)
            port_effects = effects.pop(key, [])

            returns.append(
                convert_object_to_port(
                    cls,
                    key,
                    structure_registry,
                    return_widget=return_widget,
                    effects=port_effects,
                    description=doc_param_description_map.pop(key, None),
                    label=doc_param_label_map.pop(key, None),
                    assign_widget=assign_widget,
                )
            )
    else:
        # We are dealing with a non tuple return
        if function_outs_annotation is None:
            pass

        elif function_outs_annotation.__name__ != "_empty":  # Is it not empty
            key = "return0"
            return_widget = return_widgets.pop(key, None)
            assign_widget = widgets.pop(key, None)
            port_effects = effects.pop(key, [])
            returns.append(
                convert_object_to_port(
                    function_outs_annotation,
                    "return0",
                    structure_registry,
                    assign_widget=assign_widget,
                    effects=port_effects,
                    description=doc_param_description_map.pop(key, None),
                    label=doc_param_label_map.pop(key, None),
                    return_widget=return_widget,
                )
            )

    node_name = None
    # Documentation Parsing
    if name is not None:
        node_name = name

    elif docstring.long_description:
        node_name = docstring.short_description
        description = description or docstring.long_description

    else:
        node_name = name or snake_to_title_case(function.__name__)
        description = description or docstring.short_description or "No Description"

    if widgets:
        raise DefinitionError(
            f"Could not find the following ports for the widgets in the function {function.__name__}: {','.join(widgets.keys())}. Did you forget the type hint?"
        )
    if return_widgets:
        raise DefinitionError(
            f"Could not find the following ports for the return widgets in the function {function.__name__}: {','.join(return_widgets.keys())}. Did you forget the type hint?"
        )
    if port_label_map:
        raise DefinitionError(
            f"Could not find the following ports for the labels in the function {function.__name__}: {','.join(port_label_map.keys())}. Did you forget the type hint?"
        )
    if port_description_map:
        raise DefinitionError(
            f"Could not find the following ports for the descriptions in the function {function.__name__}: {','.join(port_description_map.keys())}. Did you forget the type hint?"
        )

    x = DefinitionInput(
        **{
            "name": node_name,
            "description": description,
            "collections": collections,
            "args": args,
            "returns": returns,
            "kind": NodeKind.GENERATOR if is_generator else NodeKind.FUNCTION,
            "interfaces": interfaces,
            "portGroups": port_groups,
            "isDev": is_dev,
            "stateful": stateful,
            "isTestFor": is_test_for or [],
        }
    )

    return x
