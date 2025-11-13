"""Define"""

import collections
from enum import Enum
from typing import Callable, List, Union, get_type_hints
from rekuest_next.structures.model import (
    is_model,
    inspect_model_class,
)
from .utils import extract_annotations, is_local_var
from rekuest_next.api.schema import (
    PortInput,
    DefinitionInput,
    ActionKind,
    PortKind,
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
from typing import Optional, Any, Dict, get_origin, get_args, Annotated
import types
import typing


def is_annotated(obj: Any) -> bool:  # noqa: ANN401
    """Checks if a hint is an Annotated type

    Args:
        hint (Any): The typehint to check
        annot_type (_type_, optional): _description_. Defaults to annot_type.

    Returns:
        bool: _description_
    """
    return get_origin(obj) is Annotated


def is_union_type(cls: Any) -> bool:  # noqa: ANN401
    """Check if a class is a union"""
    # We are dealing with a 3.10 Union (PEP 646)

    return get_origin(cls) in (Union, typing.Union, types.UnionType, types.UnionType)


def is_nullable(cls: Any) -> bool:  # noqa: ANN401
    """Check if a class is nullable"""

    if is_union_type(cls):
        for arg in get_args(cls):
            if arg is type(None):
                return True

    if get_origin(cls) is Optional:
        return True

    return False


def get_non_nullable(cls: Any) -> Any:  # noqa: ANN401
    """Get the non-nullable type of a union type"""
    args = get_args(cls)

    non_nullable_args = [arg for arg in args if arg is not type(None)]
    if len(non_nullable_args) == 1:
        return non_nullable_args[0]
    else:
        return Union.__getitem__(tuple(non_nullable_args))  # type: ignore


def get_non_nullable_variant(cls: Any) -> Any:  # noqa: ANN401
    """Get the non-nullable type of a union type"""
    non_nullable_args = [arg for arg in get_args(cls) if arg is not type(None)]
    if len(non_nullable_args) == 1:
        return non_nullable_args[0]
    # We are dealing with a Union so we still use the same class
    # the logic will be handled in the union path
    # TODO: We might want to handle this better
    return cls


def is_union(cls: Any) -> bool:  # noqa: ANN401
    """Check if a class is a union"""
    if not is_union_type(cls):
        return False

    return True


def is_tuple(cls: Any) -> bool:  # noqa: ANN401
    """Check if a class is a tuple"""
    return get_origin(cls) in (tuple, typing.Tuple)


def is_list(cls: Any) -> bool:  # noqa: ANN401
    """Check if a class is a list"""
    return get_origin(cls) in (list, typing.List)


def is_dict(cls: Any) -> bool:  # noqa: ANN401
    """Check if a class is a dict"""
    return get_origin(cls) in (dict, typing.Dict, types.MappingProxyType)


def get_dict_value_cls(cls: Any) -> Any:  # noqa: ANN401
    """Get the value class of a dict"""
    return get_args(cls)[1]


def get_list_value_cls(cls: Any) -> Any:  # noqa: ANN401
    """Get the value class of a list"""
    return get_args(cls)[0]


def get_non_null_variants(cls: Any) -> List[Any]:  # noqa: ANN401
    """Get the non-null variants of a union type"""
    return [arg for arg in get_args(cls) if arg is not type(None)]


def is_bool(cls: Any) -> bool:  # noqa: ANN401
    """Check if a class is a bool"""
    if inspect.isclass(cls):
        return not issubclass(cls, Enum) and issubclass(cls, bool)
    return False


def is_float(cls: Any) -> bool:  # noqa: ANN401
    """Check if a class is a float"""
    if inspect.isclass(cls):
        return not issubclass(cls, Enum) and issubclass(cls, float)
    return False


def is_none_type(cls: Any) -> bool:  # noqa: ANN401
    """Check if a class is NoneType"""

    return cls is types.NoneType


def is_generator_type(cls: Any) -> bool:  # noqa: ANN401
    """Check if a class is a generator type"""
    if get_origin(cls) in (
        types.GeneratorType,
        typing.Generator,
        typing.AsyncGenerator,
        types.AsyncGeneratorType,
        collections.abc.Generator,  # type: ignore
        collections.abc.AsyncGenerator,  # type: ignore
    ):
        return True
    else:
        return False


def is_int(cls: Any) -> bool:  # noqa: ANN401
    """Check if a class is an int"""
    if inspect.isclass(cls):
        return not issubclass(cls, Enum) and issubclass(cls, int)
    return False


def is_str(cls: Any) -> bool:  # noqa: ANN401
    """Check if a class is a string"""
    if inspect.isclass(cls):
        return not issubclass(cls, Enum) and issubclass(cls, str)
    return False


def is_datetime(cls: Any) -> bool:  # noqa: ANN401
    """Check if a class is a datetime"""
    if inspect.isclass(cls):
        return not issubclass(cls, Enum) and (issubclass(cls, dt.datetime))
    return False


def convert_object_to_port(
    cls: Any,  # noqa: ANN401
    key: str,
    registry: StructureRegistry,
    assign_widget: AssignWidgetInput | None = None,
    return_widget: ReturnWidgetInput | None = None,
    default: Any | None = None,  # noqa: ANN401
    label: str | None = None,
    description: str | None = None,
    nullable: bool = False,
    validators: Optional[List[ValidatorInput]] = None,
    effects: Optional[List[EffectInput]] = None,
) -> PortInput:
    """
    Convert a class to an Port
    """
    if validators is None:
        validators = []
    if effects is None:
        effects = []

    if is_nullable(cls):
        # We are dealing with a union type
        # wee need to get the non-nullable-types
        # and convert hem to a new union

        non_nullable_args = [arg for arg in get_args(cls) if arg is not type(None)]
        cls = Union.__getitem__(tuple(non_nullable_args))  # type: ignore
        # TODO: We might want to handle this better

        return convert_object_to_port(
            cls=cls,
            key=key,
            registry=registry,
            default=default,
            nullable=True,
            assign_widget=assign_widget,
            label=label,
            effects=effects,
            return_widget=return_widget,
            description=description,
            validators=validators,
        )

    if is_model(cls):
        children = []

        inspected_model = inspect_model_class(cls)

        registry.register_as_model(cls, inspected_model.identifier)

        for arg in inspected_model.args:
            child = convert_object_to_port(
                cls=arg.cls,
                registry=registry,
                nullable=False,
                key=arg.key,
                default=arg.default,
                description=arg.description,
            )
            children.append(child)

        return PortInput(
            kind=PortKind.MODEL,
            assignWidget=assign_widget,
            returnWidget=return_widget,
            key=key,
            children=tuple(children),
            label=label,
            default=None,
            nullable=nullable,
            description=description or inspected_model.description,
            effects=tuple(effects),
            validators=tuple(validators),
            identifier=inspected_model.identifier,
        )

    if is_annotated(cls):
        real_type, *annotations = get_args(cls)

        (
            default,
            label,
            description,
            assign_widget,
            return_widget,
            validators,
            effects,
        ) = extract_annotations(
            annotations,
            default,
            label,
            description,
            assign_widget,
            return_widget,
            validators,
            effects,
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
        child = convert_object_to_port(
            cls=value_cls, registry=registry, nullable=False, key="..."
        )
        return PortInput(
            kind=PortKind.LIST,
            assignWidget=assign_widget,
            returnWidget=return_widget,
            key=key,
            children=tuple([child]),
            label=label,
            default=default if default else None,
            nullable=nullable,
            description=description,
            effects=tuple(effects),
            validators=tuple(validators),
        )

    if is_union(cls):
        variants = get_non_null_variants(cls)
        children: list[PortInput] = []
        for index, arg in enumerate(variants):
            child = convert_object_to_port(
                cls=arg, registry=registry, nullable=False, key=str(index)
            )
            children.append(child)

        return PortInput(
            kind=PortKind.UNION,
            assignWidget=assign_widget,
            returnWidget=return_widget,
            key=key,
            children=tuple(children),
            label=label,
            default=default,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
        )

    if is_dict(cls):
        value_cls = get_dict_value_cls(cls)
        child = convert_object_to_port(
            cls=value_cls, registry=registry, nullable=False, key="..."
        )
        return PortInput(
            kind=PortKind.DICT,
            assignWidget=assign_widget,
            returnWidget=return_widget,
            key=key,
            children=tuple([child]),
            label=label,
            default=default,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
        )

    if is_bool(cls) or (default is not None and isinstance(default, bool)):
        return PortInput(
            kind=PortKind.BOOL,
            assignWidget=assign_widget,
            returnWidget=return_widget,
            key=key,
            default=default,
            label=label,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
        )  # catch bool is subclass of int

    if is_int(cls) or (default is not None and isinstance(default, int)):
        return PortInput(
            kind=PortKind.INT,
            assignWidget=assign_widget,
            returnWidget=return_widget,
            key=key,
            default=default,
            label=label,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
        )

    if is_float(cls) or (default is not None and isinstance(default, float)):
        return PortInput(
            kind=PortKind.FLOAT,
            assignWidget=assign_widget,
            returnWidget=return_widget,
            key=key,
            default=default,
            label=label,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
        )

    if is_datetime(cls) or (default is not None and isinstance(default, dt.datetime)):
        return PortInput(
            kind=PortKind.DATE,
            assignWidget=assign_widget,
            returnWidget=return_widget,
            key=key,
            default=default,
            label=label,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
        )

    if is_str(cls) or (default is not None and isinstance(default, str)):
        return PortInput(
            kind=PortKind.STRING,
            assignWidget=assign_widget,
            returnWidget=return_widget,
            key=key,
            default=default,
            label=label,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
        )

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


GroupMap = Dict[str, List[str]]
AssignWidgetMap = Dict[str, AssignWidgetInput]
ReturnWidgetMap = Dict[str, ReturnWidgetInput]
EffectsMap = Dict[str, List[EffectInput]]


def snake_to_title_case(snake_str: str) -> str:
    """Convert a snake_case string to Title Case.

    Args:
        snake_str (str): The snake_case string to convert.
    Returns:
        str: The converted Title Case string.
    """
    # Split the string by underscores
    words = snake_str.split("_")

    # Capitalize each word
    capitalized_words = [word.capitalize() for word in words]

    # Join the words back into a single string with spaces in between
    title_case_str = " ".join(capitalized_words)

    return title_case_str


def prepare_definition(
    function: Callable[..., Any],
    structure_registry: StructureRegistry,
    widgets: Optional[AssignWidgetMap] = None,
    return_widgets: Optional[ReturnWidgetMap] = None,
    effects: Optional[EffectsMap] = None,
    port_groups: List[PortGroupInput] | None = None,
    allow_empty_doc: bool = True,
    collections: List[str] | None = None,
    interfaces: Optional[List[str]] = None,
    description: str | None = None,
    stateful: bool = False,
    is_test_for: Optional[List[str]] = None,
    port_label_map: Optional[Dict[str, str]] = None,
    port_description_map: Optional[Dict[str, str]] = None,
    validators: Optional[Dict[str, List[ValidatorInput]]] = None,
    name: str | None = None,
    omitfirst: int | None = None,
    omitlast: int | None = None,
    logo: str | None = None,
    omitkeys: list[str] | None = None,
    return_annotations: Optional[List[Any]] = None,
    allow_dev: bool = True,
    allow_annotations: bool = True,
) -> DefinitionInput:
    """Define

    Define a callable (async function, sync function, async generator, async
    generator) in the context of arkitekt and
    return its definition (as an input that can be send to the arkitekt service,
    to register the callable as a function)

    Args:
        function (Callable): The function you want to define
        structure_registry (StructureRegistry): The structure registry that should be checked against and new parameters registered within
        widgets (Dict[str, WidgetInput], optional): The widgets to use for function parameters. If none or key not present the default widget will be used.
        return_widgets ()
    """

    assert structure_registry is not None, "You need to pass a StructureRegistry"

    is_generator = inspect.isasyncgenfunction(function) or inspect.isgeneratorfunction(
        function
    )

    sig = inspect.signature(function)
    widgets = widgets or {}
    effects = effects or {}
    omitkeys = omitkeys or []
    validators = validators or {}

    port_groups = port_groups or []

    return_widgets = return_widgets or {}
    interfaces = interfaces or []
    collections = collections or []
    # Generate Args and Kwargs from the Annotation
    args: List[PortInput] = []
    returns: List[PortInput] = []

    # Docstring Parser to help with descriptions
    docstring = parse(function.__doc__ or "")

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
    doc_param_label_map: Dict[str, str] = {
        param.arg_name: param.arg_name for param in docstring.params
    }

    if docstring.many_returns:
        doc_param_description_map.update(
            {
                f"return{index}": param.description
                for index, param in enumerate(docstring.many_returns)
            }
        )
        doc_param_label_map.update(
            {
                f"return{index}": param.return_name or f"return{index}"
                for index, param in enumerate(docstring.many_returns)
            }
        )
    elif docstring.returns:
        doc_param_description_map.update({"return0": docstring.returns.description})
        doc_param_label_map.update(
            {"return0": docstring.returns.return_name or "return0"}
        )

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
                f"Could not convert Argument of function {function.__name__} to ArgPort: {value}"
            ) from e

    function_outs_annotation = type_hints.get("return", None)

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

    else:
        # We are dealing with a non tuple return
        if function_outs_annotation is None or is_none_type(function_outs_annotation):
            pass

        else:
            if is_generator_type(function_outs_annotation):
                function_outs_annotation = get_args(function_outs_annotation)[0]

            if is_tuple(function_outs_annotation):
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

    action_name = None
    # Documentation Parsing
    if name is not None:
        action_name = name

    elif docstring.long_description:
        action_name = docstring.short_description or snake_to_title_case(
            function.__name__
        )
        description = description or docstring.long_description

    else:
        action_name = name or snake_to_title_case(function.__name__)
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

    definition = DefinitionInput(
        name=action_name,
        description=description,
        collections=tuple(collections),
        args=tuple(args),
        returns=tuple(returns),
        kind=ActionKind.GENERATOR if is_generator else ActionKind.FUNCTION,
        interfaces=tuple(interfaces),
        portGroups=tuple(port_groups),
        isDev=is_dev,
        logo=logo,
        stateful=stateful,
        isTestFor=tuple(is_test_for or []),
    )

    return definition
