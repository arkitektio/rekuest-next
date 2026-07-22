"""Define"""

import collections
from enum import Enum
from typing import Callable, List, Union, get_type_hints
from rekuest_next.structures.model import (
    is_model,
    inspect_model_class,
)
from .utils import is_local_var
from rekuest_next.annotations import extract_annotations, PortAnnotations
from rekuest_next.api.schema import (
    AgentDependencyInput,
    ArgPortInput,
    ProvidesInput,
    RequiresInput,
    ReturnPortInput,
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
from docstring_parser import parse, DocstringStyle
from rekuest_next.definition.errors import DefinitionError, NonSufficientDocumentation
import datetime as dt
from rekuest_next.structures.registry import (
    StructureRegistry,
)
from rekuest_next.structures.convert import is_literal
from rekuest_next.structures.quantities import (
    is_pint_quantity,
    dimension_of,
    proposed_units_of,
    shrink_quantity,
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


def is_dependency_type(cls: Any) -> bool:  # noqa: ANN401
    """Check if a class is a dependency type"""
    if hasattr(cls, "__rekuest__dependency__"):
        dependency = getattr(cls, "__rekuest__dependency__")
        if getattr(dependency, "to_dependency_input", None) and callable(
            dependency.to_dependency_input
        ):
            return True
        else:
            raise DefinitionError(
                f"Class {cls} has a __rekuest__dependency__ attribute but it does not have a callable to_dependency_input method. Please fix this."
            )
    return False


def dependency_to_dependency_input(key: str, cls: Any) -> AgentDependencyInput:
    """Convert a dependency class to a DependencyInput"""
    dependency = getattr(cls, "__rekuest__dependency__")
    return dependency.to_dependency_input(key)


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


def convert_object_to_argport(
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
    requires: Optional[List[RequiresInput]] = None,
    provides: Optional[List[ProvidesInput]] = None,
    proposed_units: Optional[List[str]] = None,
) -> ArgPortInput:
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
        cls = Union[tuple(non_nullable_args)]  # type: ignore
        # TODO: We might want to handle this better

        return convert_object_to_argport(
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
            child = convert_object_to_argport(
                cls=arg.cls,
                registry=registry,
                nullable=False,
                key=arg.key,
                default=arg.default,
                description=arg.description,
                validators=arg.validators or [],
                label=arg.label,
            )
            children.append(child)

        return ArgPortInput(
            kind=PortKind.MODEL,
            widget=assign_widget,
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

        ann = extract_annotations(
            annotations,
            PortAnnotations(
                default=default,
                label=label,
                description=description,
                assign_widget=assign_widget,
                return_widget=return_widget,
                validators=validators,
                effects=effects,
                requires=requires,
                provides=provides,
                proposed_units=proposed_units,
            ),
        )

        return convert_object_to_argport(
            real_type,
            key,
            registry,
            assign_widget=ann.assign_widget,
            default=ann.default,
            label=ann.label,
            effects=ann.effects,
            nullable=nullable,
            validators=ann.validators,
            description=ann.description,
            requires=ann.requires,
            provides=ann.provides,
            proposed_units=ann.proposed_units,
        )

    if is_list(cls):
        value_cls = get_list_value_cls(cls)
        child = convert_object_to_argport(
            cls=value_cls, registry=registry, nullable=False, key="..."
        )
        return ArgPortInput(
            kind=PortKind.LIST,
            widget=assign_widget,
            key=key,
            children=tuple([child]),
            label=label,
            default=default if default else None,
            nullable=nullable,
            description=description,
            effects=tuple(effects),
            validators=tuple(validators),
            requires=tuple(requires) if requires else None,
        )

    if is_union(cls):
        variants = get_non_null_variants(cls)
        children: list[ArgPortInput] = []
        for index, arg in enumerate(variants):
            child = convert_object_to_argport(
                cls=arg, registry=registry, nullable=False, key=str(index)
            )
            children.append(child)

        return ArgPortInput(
            kind=PortKind.UNION,
            widget=assign_widget,
            key=key,
            children=tuple(children),
            label=label,
            default=default,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
            requires=tuple(requires) if requires else None,
        )

    if is_dict(cls):
        value_cls = get_dict_value_cls(cls)
        child = convert_object_to_argport(
            cls=value_cls, registry=registry, nullable=False, key="..."
        )
        return ArgPortInput(
            key=key,
            kind=PortKind.DICT,
            widget=assign_widget,
            children=tuple([child]),
            label=label,
            default=default,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
            requires=tuple(requires) if requires else None,
        )

    if is_literal(cls):
        # typing.Literal[...] is autoconverted to an enum port. Route through
        # the registry before the primitive checks below so a literal with a
        # string/int default isn't mistaken for a plain STRING/INT port.
        return registry.get_argport_for_cls(
            cls,
            key,
            nullable=nullable,
            description=description,
            effects=effects,
            label=label,
            default=default,
            validators=validators,
            assign_widget=assign_widget,
            requires=tuple(requires) if requires else None,
        )

    if is_bool(cls) or (default is not None and isinstance(default, bool)):
        return ArgPortInput(
            kind=PortKind.BOOL,
            widget=assign_widget,
            key=key,
            default=default,
            label=label,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
            requires=tuple(requires) if requires else None,
        )  # catch bool is subclass of int

    if is_int(cls) or (default is not None and isinstance(default, int)):
        return ArgPortInput(
            kind=PortKind.INT,
            widget=assign_widget,
            key=key,
            default=default,
            label=label,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
            requires=tuple(requires) if requires else None,
        )

    if is_float(cls) or (default is not None and isinstance(default, float)):
        return ArgPortInput(
            kind=PortKind.FLOAT,
            widget=assign_widget,
            key=key,
            default=default,
            label=label,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
            requires=tuple(requires) if requires else None,
        )

    if is_datetime(cls) or (default is not None and isinstance(default, dt.datetime)):
        return ArgPortInput(
            kind=PortKind.DATE,
            widget=assign_widget,
            key=key,
            default=default,
            label=label,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
            requires=tuple(requires) if requires else None,
        )

    if is_str(cls) or (default is not None and isinstance(default, str)):
        return ArgPortInput(
            kind=PortKind.STRING,
            widget=assign_widget,
            key=key,
            default=default,
            label=label,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
            requires=tuple(requires) if requires else None,
        )

    if is_pint_quantity(cls):
        # A kanne dimension type (Duration, ElectricPotential, ...). The wire form is a
        # pint string; reference_unit is the canonical/default unit, proposed_units the
        # UI dropdown, dimension the wiring key.
        return ArgPortInput(
            kind=PortKind.QUANTITY,
            widget=assign_widget,
            key=key,
            # A quantity default is a live pint/kanne value; shrink it to its wire
            # string ("28.6 µm") so the port default stays JSON serializable.
            default=shrink_quantity(default) if default is not None else None,
            label=label,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
            requires=tuple(requires) if requires else None,
            reference_unit=cls.reference_unit,
            proposed_units=list(proposed_units or proposed_units_of(cls)),
            dimension=dimension_of(cls),
        )

    return registry.get_argport_for_cls(
        cls,
        key,
        nullable=nullable,
        description=description,
        effects=effects,
        label=label,
        default=default,
        validators=validators,
        assign_widget=assign_widget,
        requires=tuple(requires) if requires else None,
    )


def convert_object_to_returnport(
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
    requires: Optional[List[RequiresInput]] = None,
    provides: Optional[List[ProvidesInput]] = None,
    proposed_units: Optional[List[str]] = None,
) -> ReturnPortInput:
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
        cls = Union[tuple(non_nullable_args)]  # type: ignore
        # TODO: We might want to handle this better

        return convert_object_to_returnport(
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
            child = convert_object_to_returnport(
                cls=arg.cls,
                registry=registry,
                nullable=False,
                key=arg.key,
                default=arg.default,
                description=arg.description,
                validators=arg.validators or [],
                label=arg.label,
            )
            children.append(child)

        return ReturnPortInput(
            kind=PortKind.MODEL,
            widget=return_widget,
            key=key,
            children=tuple(children),
            label=label,
            default=None,
            nullable=nullable,
            description=description or inspected_model.description,
            effects=tuple(effects),
            validators=tuple(validators),
            identifier=inspected_model.identifier,
            provides=tuple(provides) if provides else None,
        )

    if is_annotated(cls):
        real_type, *annotations = get_args(cls)

        ann = extract_annotations(
            annotations,
            PortAnnotations(
                default=default,
                label=label,
                description=description,
                assign_widget=assign_widget,
                return_widget=return_widget,
                validators=validators,
                effects=effects,
                requires=requires,
                provides=provides,
                proposed_units=proposed_units,
            ),
        )

        return convert_object_to_returnport(
            real_type,
            key,
            registry,
            assign_widget=ann.assign_widget,
            default=ann.default,
            label=ann.label,
            effects=ann.effects,
            nullable=nullable,
            validators=ann.validators,
            description=ann.description,
            requires=ann.requires,
            provides=ann.provides,
            proposed_units=ann.proposed_units,
        )

    if is_list(cls):
        value_cls = get_list_value_cls(cls)
        child = convert_object_to_returnport(
            cls=value_cls, registry=registry, nullable=False, key="..."
        )
        return ReturnPortInput(
            kind=PortKind.LIST,
            widget=return_widget,
            key=key,
            children=tuple([child]),
            label=label,
            default=default if default else None,
            nullable=nullable,
            description=description,
            effects=tuple(effects),
            validators=tuple(validators),
            provides=tuple(provides) if provides else None,
        )

    if is_union(cls):
        variants = get_non_null_variants(cls)
        children: list[ReturnPortInput] = []
        for index, arg in enumerate(variants):
            child = convert_object_to_returnport(
                cls=arg, registry=registry, nullable=False, key=str(index)
            )
            children.append(child)

        return ReturnPortInput(
            kind=PortKind.UNION,
            widget=return_widget,
            key=key,
            children=tuple(children),
            label=label,
            default=default,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
            provides=tuple(provides) if provides else None,
        )

    if is_dict(cls):
        value_cls = get_dict_value_cls(cls)
        child = convert_object_to_returnport(
            cls=value_cls, registry=registry, nullable=False, key="..."
        )
        return ReturnPortInput(
            kind=PortKind.DICT,
            widget=return_widget,
            key=key,
            children=tuple([child]),
            label=label,
            default=default,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
            provides=tuple(provides) if provides else None,
        )

    if is_literal(cls):
        # typing.Literal[...] is autoconverted to an enum port. Route through
        # the registry before the primitive checks below so a literal with a
        # string/int default isn't mistaken for a plain STRING/INT port.
        return registry.get_returnport_for_cls(
            cls,
            key,
            nullable=nullable,
            description=description,
            effects=effects,
            label=label,
            default=default,
            validators=validators,
            return_widget=return_widget,
            provides=provides,
        )

    if is_bool(cls) or (default is not None and isinstance(default, bool)):
        return ReturnPortInput(
            kind=PortKind.BOOL,
            widget=return_widget,
            key=key,
            default=default,
            label=label,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
            provides=tuple(provides) if provides else None,
        )  # catch bool is subclass of int

    if is_int(cls) or (default is not None and isinstance(default, int)):
        return ReturnPortInput(
            kind=PortKind.INT,
            widget=return_widget,
            key=key,
            default=default,
            label=label,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
            provides=tuple(provides) if provides else None,
        )

    if is_float(cls) or (default is not None and isinstance(default, float)):
        return ReturnPortInput(
            kind=PortKind.FLOAT,
            widget=return_widget,
            key=key,
            default=default,
            label=label,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
            provides=tuple(provides) if provides else None,
        )

    if is_datetime(cls) or (default is not None and isinstance(default, dt.datetime)):
        return ReturnPortInput(
            kind=PortKind.DATE,
            widget=return_widget,
            key=key,
            default=default,
            label=label,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
            provides=tuple(provides) if provides else None,
        )

    if is_str(cls) or (default is not None and isinstance(default, str)):
        return ReturnPortInput(
            kind=PortKind.STRING,
            widget=return_widget,
            key=key,
            default=default,
            label=label,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
            provides=tuple(provides) if provides else None,
        )

    if is_pint_quantity(cls):
        # A kanne dimension type produced as an output. Serializes to a pint string;
        # reference_unit is the canonical/default unit, proposed_units the UI dropdown,
        # dimension the wiring key.
        return ReturnPortInput(
            kind=PortKind.QUANTITY,
            widget=return_widget,
            key=key,
            # Shrink a live quantity default to its wire string so it stays JSON
            # serializable (mirrors the arg-port branch above).
            default=shrink_quantity(default) if default is not None else None,
            label=label,
            nullable=nullable,
            effects=tuple(effects),
            validators=tuple(validators),
            description=description,
            provides=tuple(provides) if provides else None,
            reference_unit=cls.reference_unit,
            proposed_units=list(proposed_units or proposed_units_of(cls)),
            dimension=dimension_of(cls),
        )

    return registry.get_returnport_for_cls(
        cls,
        key,
        nullable=nullable,
        description=description,
        effects=effects,
        label=label,
        default=default,
        validators=validators,
        return_widget=return_widget,
        provides=provides,
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
    is_test_for: Optional[List[str]] = None,
    port_label_map: Optional[Dict[str, str]] = None,
    port_description_map: Optional[Dict[str, str]] = None,
    validators: Optional[Dict[str, List[ValidatorInput]]] = None,
    name: str | None = None,
    omitfirst: int | None = None,
    omitlast: int | None = None,
    logo: str | None = None,
    stateful: bool = False,
    omitkeys: list[str] | None = None,
    return_annotations: Optional[List[Any]] = None,
    allow_dev: bool = True,
    allow_annotations: bool = True,
    version: Optional[str] = None,
    key: Optional[str] = None,
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
    args: List[ArgPortInput] = []
    returns: List[ReturnPortInput] = []

    # Docstring Parser to help with descriptions. ``AUTO`` tries every known
    # style (reST, Google, Numpydoc, Epydoc) and keeps the best match, so we
    # accept whatever convention the author happens to use.
    docstring = parse(function.__doc__ or "", style=DocstringStyle.AUTO)

    function_name = (
        getattr(function, "__name__", None)
        or function.__class__.__name__
        or "unknown_function"
    )

    definition_key = key or function_name

    is_dev = False

    # Whether the action carries any human-written documentation. The registered
    # name is *never* taken from the docstring (see below), so an undocumented
    # function is still perfectly registerable -- it is just flagged as a "dev"
    # (insufficiently documented) action, and rejected outright when docs are
    # required (``not allow_empty_doc``) and we are not in dev mode.
    has_documentation = bool(
        description or docstring.short_description or docstring.long_description
    )

    if not has_documentation:
        is_dev = True
        if not allow_empty_doc and not allow_dev:
            raise NonSufficientDocumentation(
                f"We are not in dev mode. Please document {function_name} with a "
                "docstring or pass an explicit description. Try a docstring :)"
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
                f"Could not find type hint for {key} in {function_name}. Please provide a type hint (or default) for this argument."
            )

        if is_dependency_type(cls):
            continue

        if is_local_var(cls):
            continue

        try:
            args.append(
                convert_object_to_argport(
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
                f"Could not convert Argument of function {function_name} to ArgPort: {value}"
            ) from e

    function_outs_annotation = type_hints.get("return", None)

    if return_annotations:
        for index, cls in enumerate(return_annotations):
            key = f"return{index}"
            return_widget = return_widgets.pop(key, None)
            assign_widget = widgets.pop(key, None)
            port_effects = effects.pop(key, None)

            returns.append(
                convert_object_to_returnport(
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

            if is_dependency_type(function_outs_annotation):
                raise DefinitionError(
                    f"Function {function_name} has a return type that is a dependency. This is not allowed. Please change the return type."
                )

            if is_tuple(function_outs_annotation):
                for index, cls in enumerate(get_args(function_outs_annotation)):
                    key = f"return{index}"
                    return_widget = return_widgets.pop(key, None)
                    assign_widget = widgets.pop(key, None)
                    port_effects = effects.pop(key, [])

                    returns.append(
                        convert_object_to_returnport(
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
                    convert_object_to_returnport(
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

    # The registered name is NEVER inferred from the docstring. Using the
    # docstring summary line as the action name was being misused, so the name
    # comes only from an explicit ``name`` argument or, failing that, the
    # function's own name. The docstring is reserved purely for the description.
    action_name = name or snake_to_title_case(function_name)

    # Build the description from the docstring, joining the summary line
    # (short description) and the body (long description) back together. This
    # works for any docstring style (reST, Google, Numpydoc, Epydoc) because
    # ``parse`` auto-detects the style above.
    if description is None:
        doc_parts = [
            part
            for part in (docstring.short_description, docstring.long_description)
            if part
        ]
        description = "\n\n".join(doc_parts) if doc_parts else "No Description"

    if widgets:
        raise DefinitionError(
            f"Could not find the following ports for the widgets in the function {function_name}: {','.join(widgets.keys())}. Did you forget the type hint?"
        )
    if return_widgets:
        raise DefinitionError(
            f"Could not find the following ports for the return widgets in the function {function_name}: {','.join(return_widgets.keys())}. Did you forget the type hint?"
        )
    if port_label_map:
        raise DefinitionError(
            f"Could not find the following ports for the labels in the function {function_name}: {','.join(port_label_map.keys())}. Did you forget the type hint?"
        )
    if port_description_map:
        raise DefinitionError(
            f"Could not find the following ports for the descriptions in the function {function_name}: {','.join(port_description_map.keys())}. Did you forget the type hint?"
        )

    definition = DefinitionInput(
        key=definition_key,
        version=version or "1",
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
