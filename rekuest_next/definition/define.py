from enum import Enum
from typing import Callable, List, Tuple, Type, Union

from rekuest_next.definition.guards import cls_is_union
from .utils import get_type_hints, is_annotated
import inflection
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
)
import inspect
from docstring_parser import parse
from rekuest_next.definition.errors import DefinitionError, NonSufficientDocumentation
import datetime as dt
from rekuest_next.structures.registry import (
    StructureRegistry,
)
from typing import (
    Protocol,
    runtime_checkable,
    Optional,
    List,
    Any,
    Dict,
    get_origin,
    get_args,
)
import types
import typing


def convert_child_to_childport(
    cls: Type,
    registry: StructureRegistry,
    nullable: bool = False,
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

    if is_annotated(cls):
        real_type = cls.__args__[0]

        return convert_child_to_childport(
            real_type,
            registry,
            nullable=nullable,
        )

    if cls.__module__ == "typing":
        if hasattr(cls, "_name"):
            # We are dealing with a Typing Var?
            if cls._name == "List":
                child, nested_converter = convert_child_to_childport(
                    cls.__args__[0], registry, nullable=False
                )

                return (
                    ChildPortInput(
                        kind=PortKind.LIST,
                        child=child,
                        scope=PortScope.GLOBAL,
                        nullable=nullable,
                    ),
                    lambda default: (
                        [nested_converter(ndefault) for ndefault in default]
                        if default
                        else None
                    ),
                )

            if cls._name == "Dict":
                child, nested_converter = convert_child_to_childport(
                    cls.__args__[1], "omit", registry, nullable=False
                )
                return (
                    ChildPortInput(
                        kind=PortKind.DICT,
                        child=child,
                        scope=PortScope.GLOBAL,
                        nullable=nullable,
                    ),
                    lambda default: (
                        {
                            key: item in nested_converter(item)
                            for key, item in default.items()
                        }
                        if default
                        else None
                    ),
                )

        if hasattr(cls, "__args__"):
            if cls.__args__[1] == type(None):
                return convert_child_to_childport(
                    cls.__args__[0], registry, nullable=True
                )

    if inspect.isclass(cls):
        # Generic Cases

        if not issubclass(cls, Enum) and issubclass(cls, bool):
            t = ChildPortInput(
                kind=PortKind.BOOL,
                nullable=nullable,
                scope=PortScope.GLOBAL,
            )  # catch bool is subclass of int
            return t, str

        if not issubclass(cls, Enum) and issubclass(cls, float):
            return (
                ChildPortInput(
                    kind=PortKind.FLOAT,
                    nullable=nullable,
                    scope=PortScope.GLOBAL,
                ),
                float,
            )

        if not issubclass(cls, Enum) and issubclass(cls, int):
            return (
                ChildPortInput(
                    kind=PortKind.INT,
                    nullable=nullable,
                    scope=PortScope.GLOBAL,
                ),
                int,
            )

        if not issubclass(cls, Enum) and (issubclass(cls, dt.datetime)):
            return (
                ChildPortInput(
                    kind=PortKind.DATE,
                    nullable=nullable,
                    scope=PortScope.GLOBAL,
                ),
                lambda x: x.isoformat(),
            )

        if not issubclass(cls, Enum) and issubclass(cls, str):
            return (
                ChildPortInput(
                    kind=PortKind.STRING,
                    nullable=nullable,
                    scope=PortScope.GLOBAL,
                ),
                str,
            )

    return registry.get_child_port_and_default_converter_for_cls(cls, nullable=nullable)


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
    effects: Optional[List[EffectInput]] = None,
    groups: Optional[List[str]] = None,
) -> PortInput:
    """
    Convert a class to an Port
    """
    if is_annotated(cls):
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
            groups=groups,
        )

    if cls.__module__ == "typing":
        if hasattr(cls, "_name"):
            # We are dealing with a Typing Var?
            if cls._name == "List":
                child, converter = convert_child_to_childport(
                    cls.__args__[0], registry, nullable=False
                )
                return PortInput(
                    kind=PortKind.LIST,
                    assignWidget=assign_widget,
                    returnWidget=return_widget,
                    scope=PortScope.GLOBAL,
                    key=key,
                    child=child,
                    label=label,
                    default=[converter(item) for item in default] if default else None,
                    nullable=nullable,
                    effects=effects,
                    description=description,
                    groups=groups,
                )

            if cls_is_union(cls):
                args = get_args(cls)
                if len(args) == 2 and args[0] == type(None) or args[1] == type(None):
                    if args[0] == type(None):
                        cls = args[1]
                    if args[1] == type(None):
                        cls = args[0]

                    return convert_object_to_port(
                        cls,
                        key,
                        registry,
                        default=default,
                        nullable=True,
                        assign_widget=assign_widget,
                        label=label,
                        effects=effects,
                        return_widget=return_widget,
                        description=description,
                        groups=groups,
                    )
                else:
                    # We are dealing with a "Real union"
                    args = get_args(cls)
                    nullable = False
                    variants = []
                    for arg in args:
                        if arg == type(None):
                            nullable = True
                        child, converter = convert_child_to_childport(
                            arg, registry, nullable=False
                        )
                        variants.append(child)

                    return PortInput(
                        kind=PortKind.UNION,
                        assignWidget=assign_widget,
                        returnWidget=return_widget,
                        scope=PortScope.GLOBAL,
                        key=key,
                        variants=variants,
                        label=label,
                        default=None,  # TODO: SHould fix based on predicate of default
                        nullable=nullable,
                        effects=effects,
                        description=description,
                        groups=groups,
                    )

            if cls._name == "Dict":
                child, converter = convert_child_to_childport(
                    cls.__args__[1], registry, nullable=False
                )
                return PortInput(
                    kind=PortKind.DICT,
                    assignWidget=assign_widget,
                    scope=PortScope.GLOBAL,
                    returnWidget=return_widget,
                    key=key,
                    child=child,
                    label=label,
                    default=(
                        {key: converter(item) for key, item in default.items()}
                        if default
                        else None
                    ),
                    nullable=nullable,
                    effects=effects,
                    description=description,
                    groups=groups,
                )

            if cls._name == "Union":
                raise NotImplementedError("Union is not supported yet")

        if hasattr(cls, "__args__"):
            if cls.__args__[1] == type(None):
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
                    groups=groups,
                )

    if inspect.isclass(cls):
        # Generic Cases

        if not issubclass(cls, Enum) and (
            issubclass(cls, bool) or (default is not None and isinstance(default, bool))
        ):
            t = PortInput(
                kind=PortKind.BOOL,
                scope=PortScope.GLOBAL,
                assignWidget=assign_widget,
                returnWidget=return_widget,
                key=key,
                default=default,
                label=label,
                nullable=nullable,
                effects=effects,
                description=description,
                groups=groups,
            )  # catch bool is subclass of int
            return t

        if not issubclass(cls, Enum) and (
            issubclass(cls, int) or (default is not None and isinstance(default, int))
        ):
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
                description=description,
                groups=groups,
            )

        if not issubclass(cls, Enum) and (
            issubclass(cls, float)
            or (default is not None and isinstance(default, float))
        ):
            return PortInput(
                kind=PortKind.FLOAT,
                assignWidget=assign_widget,
                returnWidget=return_widget,
                scope=PortScope.GLOBAL,
                key=key,
                default=default,
                label=label,
                nullable=nullable,
                effects=effects,
                description=description,
                groups=groups,
            )

        if not issubclass(cls, Enum) and (
            issubclass(cls, dt.datetime)
            or (default is not None and isinstance(default, dt.datetime))
        ):
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
                description=description,
                groups=groups,
            )

        if not issubclass(cls, Enum) and (
            issubclass(cls, str) or (default is not None and isinstance(default, str))
        ):
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
                description=description,
                groups=groups,
            )

    return registry.get_port_for_cls(
        cls,
        key,
        nullable=nullable,
        description=description,
        groups=groups,
        effects=effects,
        label=label,
        default=default,
        assign_widget=assign_widget,
        return_widget=return_widget,
    )


GroupMap = Dict[str, List[str]]
AssignWidgetMap = Dict[str, List[AssignWidgetInput]]
ReturnWidgetMap = Dict[str, List[ReturnWidgetInput]]
EffectsMap = Dict[str, List[EffectInput]]


def prepare_definition(
    function: Callable,
    structure_registry: StructureRegistry,
    widgets: Optional[AssignWidgetMap] = None,
    return_widgets: Optional[ReturnWidgetMap] = None,
    groups: Optional[GroupMap] = None,
    effects: Optional[EffectsMap] = None,
    port_groups: List[PortGroupInput] = None,
    allow_empty_doc=True,
    collections: List[str] = [],
    interfaces: Optional[List[str]] = None,
    description: str = None,
    is_test_for: Optional[List[str]] = None,
    port_label_map: Optional[Dict[str, str]] = None,
    port_description_map: Optional[Dict[str, str]] = None,
    name: str = None,
    omitfirst=None,
    omitlast=None,
    omitkeys=[],
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

    port_groups = port_groups or []
    port_groups_name = [i.key for i in port_groups]
    groups = groups or {}
    for key, grouplist in groups.items():
        for group in grouplist:
            if group not in port_groups_name:
                raise DefinitionError(
                    f"Error mapping {group} to a group in port groups for port {key}:  Please define a PortGroup for {group}"
                )

    return_widgets = return_widgets or {}
    interfaces = interfaces or []
    collections = collections or []
    # Generate Args and Kwargs from the Annotation
    args: List[PortInput] = []
    returns: List[PortInput] = []

    # Docstring Parser to help with descriptions
    docstring = parse(function.__doc__)
    if not docstring.short_description and name is None:
        raise NonSufficientDocumentation(
            f"Either provide a name or better document {function.__name__}. Try docstring"
        )

    if not docstring.long_description and description is None and not allow_empty_doc:
        raise NonSufficientDocumentation(
            f"Please provide a description or better document  {function.__name__}. Try docstring"
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
        port_effects = effects.pop(key, None)
        return_widget = return_widgets.pop(key, None)
        default = value.default if value.default != inspect.Parameter.empty else None
        cls = type_hints.get(key, type(default) if default is not None else None)
        this_port_groups = groups.get(key, None)

        if cls is None:
            raise DefinitionError(
                f"Could not find type hint for {key} in {function.__name__}. Please provide a type hint (or default) for this argument."
            )

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
                    groups=this_port_groups,
                )
            )
        except Exception as e:
            raise DefinitionError(
                f"Could not convert Argument of function {function.__name__} to"
                f" ArgPort: {value}"
            ) from e

    function_outs_annotation = sig.return_annotation

    if hasattr(function_outs_annotation, "_name"):
        if function_outs_annotation._name == "Tuple":
            try:
                for index, cls in enumerate(function_outs_annotation.__args__):
                    key = f"return{index}"
                    return_widget = return_widgets.pop(key, None)
                    assign_widget = widgets.pop(key, None)
                    port_effects = effects.pop(key, None)
                    this_port_groups = groups.pop(key, None)

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
                            groups=this_port_groups,
                        )
                    )
            except Exception as e:
                raise DefinitionError(
                    f"Could not convert Return of function {function.__name__} to"
                    f" ArgPort: {cls}"
                ) from e
        else:
            try:
                key = "return0"
                return_widget = return_widgets.pop(key, None)
                assign_widget = widgets.pop(key, None)
                this_port_groups = groups.get(key, None)
                port_effects = effects.pop(key, None)
                returns.append(
                    convert_object_to_port(
                        function_outs_annotation,
                        key,
                        structure_registry,
                        return_widget=return_widget,
                        effects=port_effects,
                        description=doc_param_description_map.pop(key, None),
                        label=doc_param_label_map.pop(key, None),
                        assign_widget=assign_widget,
                        groups=this_port_groups,
                    )
                )  # Other types will be converted to normal lists and shit
            except Exception as e:
                raise DefinitionError(
                    f"Could not convert Return of function {function.__name__} to"
                    f" ArgPort: {function_outs_annotation}"
                ) from e
    else:
        # We are dealing with a non tuple return
        if function_outs_annotation is None:
            pass

        elif function_outs_annotation.__name__ != "_empty":  # Is it not empty
            key = "return0"
            return_widget = return_widgets.pop(key, None)
            assign_widget = widgets.pop(key, None)
            this_port_groups = groups.pop(key, None)
            port_effects = effects.pop(key, None)
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
                    groups=this_port_groups,
                )
            )

    # Documentation Parsing

    name = name or docstring.short_description or function.__name__
    description = description or docstring.long_description or "No Description"

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
            "name": name,
            "description": description,
            "collections": collections,
            "args": args,
            "returns": returns,
            "kind": NodeKind.GENERATOR if is_generator else NodeKind.FUNCTION,
            "interfaces": interfaces,
            "portGroups": port_groups,
            "isTestFor": is_test_for,
        }
    )

    return x
