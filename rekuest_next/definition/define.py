"""Define"""

import collections
from enum import Enum
from typing import Union, get_type_hints
from collections.abc import Callable
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
    TestTargetInput,
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
from typing import Optional, Any, Literal, cast, get_origin, get_args, Annotated
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
    return get_origin(cls) in (tuple, tuple)


def is_list(cls: Any) -> bool:  # noqa: ANN401
    """Check if a class is a list"""
    return get_origin(cls) in (list, list)


def is_dict(cls: Any) -> bool:  # noqa: ANN401
    """Check if a class is a dict"""
    return get_origin(cls) in (dict, dict, types.MappingProxyType)


def get_dict_value_cls(cls: Any) -> Any:  # noqa: ANN401
    """Get the value class of a dict"""
    return get_args(cls)[1]


def get_list_value_cls(cls: Any) -> Any:  # noqa: ANN401
    """Get the value class of a list"""
    return get_args(cls)[0]


def get_non_null_variants(cls: Any) -> list[Any]:  # noqa: ANN401
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


PortDirection = Literal["arg", "return"]


def _port_cls_for(
    direction: PortDirection,
) -> type[ArgPortInput] | type[ReturnPortInput]:
    return ArgPortInput if direction == "arg" else ReturnPortInput


def convert_object_to_port(
    cls: Any,  # noqa: ANN401
    key: str,
    registry: StructureRegistry,
    direction: PortDirection,
    assign_widget: AssignWidgetInput | None = None,
    return_widget: ReturnWidgetInput | None = None,
    **kwargs: Any,  # noqa: ANN401
) -> ArgPortInput | ReturnPortInput:
    """Convert a Python type hint into a port (see :func:`_convert_object_to_port`).

    A ``ChoiceWidget`` carries the port's choices on the client only; the server keeps
    choices on the port, so they are promoted here when the port has none of its own.
    """
    port = _convert_object_to_port(
        cls, key, registry, direction, assign_widget=assign_widget, return_widget=return_widget, **kwargs
    )
    widget = assign_widget if direction == "arg" else return_widget
    carried = getattr(widget, "choices", None)
    if carried and not port.choices:
        port = port.model_copy(update={"choices": tuple(carried)})
    return port


def _convert_object_to_port(
    cls: Any,  # noqa: ANN401
    key: str,
    registry: StructureRegistry,
    direction: PortDirection,
    assign_widget: AssignWidgetInput | None = None,
    return_widget: ReturnWidgetInput | None = None,
    default: Any | None = None,  # noqa: ANN401
    label: str | None = None,
    description: str | None = None,
    nullable: bool = False,
    validators: list[ValidatorInput] | None = None,
    effects: list[EffectInput] | None = None,
    requires: list[RequiresInput] | None = None,
    provides: list[ProvidesInput] | None = None,
    proposed_units: list[str] | None = None,
) -> ArgPortInput | ReturnPortInput:
    """Convert a Python type hint into an arg or return port.

    Arg and return ports are built identically except for the port class, which
    widget applies (``assign_widget`` vs ``return_widget``) and which search
    descriptors they carry (``requires`` vs ``provides``).
    """
    validators = validators or []
    effects = effects or []
    port_cls = _port_cls_for(direction)
    is_arg = direction == "arg"
    widget = assign_widget if is_arg else return_widget
    # Return ports carry neither a default nor validators on the server, so those
    # are only passed along for arg ports.
    direction_kwargs: dict[str, Any] = (
        {
            "requires": tuple(requires) if requires else None,
            "default": default,
            "validators": tuple(validators),
        }
        if is_arg
        else {"provides": tuple(provides) if provides else None}
    )

    def recurse(sub_cls: Any, sub_key: str, **overrides: Any) -> Any:  # noqa: ANN401
        return convert_object_to_port(
            sub_cls, sub_key, registry, direction, **overrides
        )

    def make(kind: PortKind, **extra: Any) -> ArgPortInput | ReturnPortInput:  # noqa: ANN401
        fields: dict[str, Any] = dict(
            kind=kind,
            widget=widget,
            key=key,
            label=label,
            nullable=nullable,
            description=description,
            effects=tuple(effects),
            **direction_kwargs,
        )
        fields.update(extra)
        if not is_arg:
            # Return ports carry neither a default nor validators on the server.
            fields.pop("default", None)
            fields.pop("validators", None)
        return port_cls(**fields)

    if is_nullable(cls):
        # Strip ``None`` out of the union and build the remaining type as a
        # nullable port.
        non_nullable_args = [arg for arg in get_args(cls) if arg is not type(None)]
        return recurse(
            Union[tuple(non_nullable_args)],  # type: ignore[arg-type]  # noqa: UP007 - built from a runtime tuple
            key,
            default=default,
            nullable=True,
            assign_widget=assign_widget,
            return_widget=return_widget,
            label=label,
            effects=effects,
            description=description,
            validators=validators,
            requires=requires,
            provides=provides,
            proposed_units=proposed_units,
        )

    if is_model(cls):
        inspected_model = inspect_model_class(cls)
        registry.register_as_model(cls, inspected_model.identifier)
        children = [
            recurse(
                arg.cls,
                arg.key,
                nullable=False,
                default=arg.default,
                description=arg.description,
                validators=arg.validators or [],
                label=arg.label,
            )
            for arg in inspected_model.args
        ]
        return make(
            PortKind.MODEL,
            children=tuple(children),
            default=None,
            description=description or inspected_model.description,
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
        return recurse(
            real_type,
            key,
            assign_widget=ann.assign_widget,
            return_widget=ann.return_widget,
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
        child = recurse(get_list_value_cls(cls), "...", nullable=False)
        return make(
            PortKind.LIST, children=(child,), default=default if default else None
        )

    if is_union(cls):
        children = [
            recurse(arg, str(index), nullable=False)
            for index, arg in enumerate(get_non_null_variants(cls))
        ]
        return make(PortKind.UNION, children=tuple(children))

    if is_dict(cls):
        child = recurse(get_dict_value_cls(cls), "...", nullable=False)
        return make(PortKind.DICT, children=(child,))

    registry_kwargs: dict[str, Any] = dict(
        nullable=nullable,
        description=description,
        effects=effects,
        label=label,
        default=default,
        validators=validators,
    )
    if is_arg:
        registry_kwargs.update(assign_widget=assign_widget, requires=requires)
    else:
        registry_kwargs.update(return_widget=return_widget, provides=provides)

    if is_literal(cls):
        # typing.Literal[...] is autoconverted to an enum port. Route through
        # the registry before the primitive checks below so a literal with a
        # string/int default isn't mistaken for a plain STRING/INT port.
        return registry.get_port_for_cls(cls, key, direction, **registry_kwargs)

    # bool is a subclass of int, so it must be checked first.
    if is_bool(cls) or (default is not None and isinstance(default, bool)):
        return make(PortKind.BOOL)
    if is_int(cls) or (default is not None and isinstance(default, int)):
        return make(PortKind.INT)
    if is_float(cls) or (default is not None and isinstance(default, float)):
        return make(PortKind.FLOAT)
    if is_datetime(cls) or (default is not None and isinstance(default, dt.datetime)):
        return make(PortKind.DATE)
    if is_str(cls) or (default is not None and isinstance(default, str)):
        return make(PortKind.STRING)

    if is_pint_quantity(cls):
        # A kanne dimension type (Duration, ElectricPotential, ...). The wire
        # form is a pint string; reference_unit is the canonical/default unit,
        # proposed_units the UI dropdown, dimension the wiring key. A live
        # quantity default is shrunk to its wire string ("28.6 µm") so the port
        # default stays JSON serializable.
        return make(
            PortKind.QUANTITY,
            default=shrink_quantity(default) if default is not None else None,
            reference_unit=cls.reference_unit,
            proposed_units=list(proposed_units or proposed_units_of(cls)),
            dimension=dimension_of(cls),
        )

    return registry.get_port_for_cls(cls, key, direction, **registry_kwargs)


def convert_object_to_argport(
    cls: Any,  # noqa: ANN401
    key: str,
    registry: StructureRegistry,
    **kwargs: Any,  # noqa: ANN401
) -> ArgPortInput:
    """Convert a type hint into an :class:`ArgPortInput` (see :func:`convert_object_to_port`)."""
    return cast(
        ArgPortInput, convert_object_to_port(cls, key, registry, "arg", **kwargs)
    )


def convert_object_to_returnport(
    cls: Any,  # noqa: ANN401
    key: str,
    registry: StructureRegistry,
    **kwargs: Any,  # noqa: ANN401
) -> ReturnPortInput:
    """Convert a type hint into a :class:`ReturnPortInput` (see :func:`convert_object_to_port`)."""
    return cast(
        ReturnPortInput, convert_object_to_port(cls, key, registry, "return", **kwargs)
    )


GroupMap = dict[str, list[str]]
AssignWidgetMap = dict[str, AssignWidgetInput]
ReturnWidgetMap = dict[str, ReturnWidgetInput]
EffectsMap = dict[str, list[EffectInput]]


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
    widgets: AssignWidgetMap | None = None,
    return_widgets: ReturnWidgetMap | None = None,
    effects: EffectsMap | None = None,
    port_groups: list[PortGroupInput] | None = None,
    allow_empty_doc: bool = True,
    collections: list[str] | None = None,
    description: str | None = None,
    is_test_for: list[TestTargetInput] | None = None,
    validators: dict[str, list[ValidatorInput]] | None = None,
    name: str | None = None,
    omitfirst: int | None = None,
    stateful: bool = False,
    omitkeys: list[str] | None = None,
    return_annotations: list[Any] | None = None,
    allow_dev: bool = True,
    allow_annotations: bool = True,
    version: str | None = None,
    key: str | None = None,
    catalogs: list[str] | None = None,
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
    # Per-port maps are consumed (popped) below; copy so the caller's dicts
    # survive the call.
    widgets = dict(widgets or {})
    effects = dict(effects or {})
    validators = dict(validators or {})
    return_widgets = dict(return_widgets or {})
    omitkeys = omitkeys or []
    port_groups = port_groups or []
    collections = collections or []
    # Generate Args and Kwargs from the Annotation
    args: list[ArgPortInput] = []
    returns: list[ReturnPortInput] = []

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
    doc_param_label_map: dict[str, str] = {
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

    for index, (key, value) in enumerate(function_ins_annotation.items()):
        # We can skip arguments if the builder is going to provide additional arguments
        if omitfirst is not None and index < omitfirst:
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

    definition = DefinitionInput(
        key=definition_key,
        version=version or "1",
        name=action_name,
        description=description,
        collections=tuple(collections),
        args=tuple(args),
        returns=tuple(returns),
        kind=ActionKind.GENERATOR if is_generator else ActionKind.FUNCTION,
        portGroups=tuple(port_groups),
        isDev=is_dev,
        stateful=stateful,
        isTestFor=tuple(is_test_for or []),
        catalogs=tuple(catalogs) if catalogs else None,
    )

    return definition
