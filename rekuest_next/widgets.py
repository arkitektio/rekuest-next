"""Some basic helpers to create common widgets."""

from typing import get_args

from pydantic import Field

from rekuest_next.api.schema import (
    AssignWidgetInput,
    ChoiceAssignWidgetInput,
    ChoiceInput,
    ChoiceReturnWidgetInput,
    ComponentPropInput,
    ArgPortInput,
    CustomAssignWidgetInput,
    CustomReturnWidgetInput,
    ProxyAssignWidgetInput,
    ReturnWidgetInput,
    SearchAssignWidgetInput,
    SliderAssignWidgetInput,
    StateAccessorInput,
    StateChoiceAssignWidgetInput,
    StringAssignWidgetInput,
    UtilCallInput,
    ValidatorInput,
    EffectInput,
    EffectKind,
)
from rekuest_next.blok.parser import coerce_util_call, normalize_expression
from rekuest_next.structures.types import JSONSerializable
from rekuest_next.scalars import SearchQuery
from rekuest_next.traits.calls import infer_dependencies


ASSIGN_WIDGET_INPUT_TYPES: tuple[type, ...] = get_args(get_args(AssignWidgetInput)[0])
"""The member classes of the ``AssignWidgetInput`` discriminated union."""

RETURN_WIDGET_INPUT_TYPES: tuple[type, ...] = get_args(get_args(ReturnWidgetInput)[0])
"""The member classes of the ``ReturnWidgetInput`` discriminated union."""


def is_assign_widget_input(value: object) -> bool:
    """Whether ``value`` is one of the assign widget inputs."""
    return isinstance(value, ASSIGN_WIDGET_INPUT_TYPES)


def is_return_widget_input(value: object) -> bool:
    """Whether ``value`` is one of the return widget inputs."""
    return isinstance(value, RETURN_WIDGET_INPUT_TYPES)


class ChoiceAssignWidgetWithChoices(ChoiceAssignWidgetInput):
    """A CHOICE assign widget that also carries the port's choices.

    The server keeps choices on the port, not on the widget, so the definition builder
    promotes ``choices`` onto the port and they are never serialised with the widget.
    """

    choices: tuple[ChoiceInput, ...] = Field(default=(), exclude=True)


class ChoiceReturnWidgetWithChoices(ChoiceReturnWidgetInput):
    """A CHOICE return widget that also carries the port's choices (see above)."""

    choices: tuple[ChoiceInput, ...] = Field(default=(), exclude=True)


def _to_choices(choices: "list[str] | str | list[ChoiceInput] | tuple[ChoiceInput, ...]") -> tuple[ChoiceInput, ...]:
    items = [choices] if isinstance(choices, str) else list(choices)
    return tuple(
        choice if isinstance(choice, ChoiceInput) else ChoiceInput(value=str(choice), label=str(choice))
        for choice in items
    )



def SliderWidget(
    min: int | None = None, max: int | None = None, step: int | None = None
) -> AssignWidgetInput:
    """Generate a slider widget.

    Args:
        min (int, optional): The mininum value. Defaults to None.
        max (int, optional): The maximum value. Defaults to None.

    Returns:
        WidgetInput: _description_
    """
    return SliderAssignWidgetInput(min=min, max=max, step=step)


def SearchWidget(
    query: SearchQuery | str,
    ward: str,
    dependencies: list[str] | None = None,
    filters: list[ArgPortInput] | None = None,
) -> AssignWidgetInput:
    (
        """Generte a search widget.

    A search widget is a widget that allows the user to search for a specifc
    structure utilizing a GraphQL query and running it on a ward (a frontend 
    registered helper that can run the query). The query needs to follow
    the SearchQuery type.

    Args:
        query (SearchQuery): The serach query as a search query object or string
        ward (str): The ward key

    Returns:
        WidgetInput: _description_
    """
        """P"""
    )
    return SearchAssignWidgetInput(
        query=SearchQuery.validate(query),
        ward=ward,
        dependencies=tuple(dependencies) if dependencies else None,
        filters=tuple(filters) if filters else None,
    )


def StringWidget(as_paragraph: bool = False) -> AssignWidgetInput:
    """Generate a string widget.

    Args:
        as_paragraph (bool, optional): Should we render the string as a paragraph.Defaults to False.

    Returns:
        WidgetInput: _description_
    """
    return StringAssignWidgetInput(as_paragraph=as_paragraph)


def ParagraphWidget() -> AssignWidgetInput:
    """Generate a string widget.

    Args:
        as_paragraph (bool, optional): Should we render the string as a paragraph.Defaults to False.

    Returns:
        WidgetInput: _description_
    """
    return StringAssignWidgetInput(as_paragraph=True)


def CustomWidget(
    component: str,
    props: list[ComponentPropInput] | None = None,
    dependencies: list[str] | None = None,
    fallback: AssignWidgetInput | None = None,
) -> AssignWidgetInput:
    """Generate a custom widget.

    A custom widget is a component of the UI's catalog rendered as the port's
    widget. The port value is in scope as ``value``; ``props`` may reference
    ``value`` and the ``dependencies`` through value paths or pure util calls
    (agent calls are not allowed).

    Args:
        component (str): The catalog component to render
        props (list[ComponentPropInput], optional): Props passed to the component
        dependencies (list[str], optional): Other ports the props may reference
        fallback (AssignWidgetInput, optional): Widget to render when the UI has
            no such component in its catalog

    Returns:
        AssignWidgetInput: The widget input
    """
    return CustomAssignWidgetInput(
        component=component,
        props=tuple(props) if props else None,
        dependencies=tuple(dependencies) if dependencies else None,
        fallback=fallback,
    )


def CustomReturnWidget(
    component: str, props: list[ComponentPropInput] | None = None
) -> ReturnWidgetInput:
    """Generate a custom return widget.

    A custom return widget is a component of the UI's catalog rendered with the
    returned value in scope as ``value``. ``props`` may only reference ``value``.

    Args:
        component (str): The catalog component to render
        props (list[ComponentPropInput], optional): Props passed to the component

    Returns:
        ReturnWidgetInput: The widget input
    """
    return CustomReturnWidgetInput(
        component=component,
        props=tuple(props) if props else None,
    )


def ChoiceReturnWidget(choices: list[ChoiceInput]) -> ReturnWidgetInput:
    """A choice return widget.

    A choice return widget is a widget that renderes a list of choices with the
    value of the choice being highlighted.

    Args:
        choices (List[ChoiceInput]): The choices

    Returns:
        ReturnWidgetInput: _description_
    """
    return ChoiceReturnWidgetWithChoices(choices=_to_choices(choices))


def ChoiceWidget(choices: list[str] | str | list[ChoiceInput]) -> AssignWidgetInput:
    """A choice widget.

    A choice widget is a widget that renders a list of choices with the
    value of the choice being highlighted.

    Args:
        choices (list[ChoiceInput]): The choices

    Returns:
        AssignWidgetInput: The widget input
    """
    return ChoiceAssignWidgetWithChoices(choices=_to_choices(choices))


def ProxyWidget(
    dependency: str, action: str | None = None, arg: str | None = None
) -> AssignWidgetInput:
    """A forward widget.

    A forward widget is a widget that takes the widget of a dependency and sets it here. This is useful if you are want to use the same available
    sleectors (like state) of the agent but in a different function.

    Args:
        arg_path (str): The path to the argument to forward the widget from, in the format "dependency_name.arg_name"
        listify (bool): Whether to wrap the forwarded widget in a list (useful if the target argument expects a list but the source is a single value)
    """
    if not action or not arg:
        raise ValueError(
            "You need to provide both an action and an arg for the ProxyWidget"
        )

    return ProxyAssignWidgetInput(
        target_dependency=dependency,
        target_action=action,
        target_port=arg,
    )


def withStateChoices(
    state_path: str,
    accessors: list[StateAccessorInput] | None = None,
) -> AssignWidgetInput:
    """A choice widget with choices from a state path.

    A choice widget is a widget that renders a list of choices with the
    value of the choice being highlighted. The choices are taken from a state
    path.

    Args:
        state_path (str): The state path to take the choices from
        dependency (str | None): The dependency for the widget
        accessors (list[StateAccessorInput] | None): The state accessor inputs (if not provided, it will be assumed that the state is a list of choices with only a value, or an array with {key: key, value: value, description?: description} structure)
    """

    assert len(state_path.split(".")) >= 2, (
        "state_path needs to be in the format 'dependency.statename.variable....' or  'self.statename.variable....'"
    )

    dependency = state_path.split(".")[0]
    if dependency == "self":
        dependency = None

    rest_path = ".".join(state_path.split(".")[1:])

    return StateChoiceAssignWidgetInput(
        state_path=rest_path,
        dependency=dependency,
        state_accessors=tuple(accessors) if accessors else None,
    )


def withChoices(*choices: ChoiceInput | JSONSerializable) -> AssignWidgetInput:
    """A decorator to add choices to a widget.

    Args:
        choices (List[ChoiceInput]): The choices

    Returns:
        AssignWidgetInput: The widget input
    """
    if not choices:
        raise ValueError("You need to provide at least one choice")

    parsed_choices: list[ChoiceInput] = []

    for choice in choices:
        if not isinstance(choice, ChoiceInput):
            choice = ChoiceInput(value=str(choice), label=str(choice))
        parsed_choices.append(choice)

    return ChoiceAssignWidgetWithChoices(choices=tuple(parsed_choices))


def withValidator(
    call: str | UtilCallInput,
    error_message: str | None = None,
    label: str | None = None,
    dependencies: list[str] | None = None,
) -> ValidatorInput:
    """Build a validator for a port from a pure blok call.

    The call is evaluated by the UI against its function catalog and must return a
    boolean meaning "valid". ``value`` refers to the port's own value; other names
    refer to sibling ports and are subscribed to automatically.

    Args:
        call: An expression such as ``"value > 3"``, ``"gt(value, other.min)"`` or
            ``"len(value) > 0 and value[0] != 'x'"``, or a ready :class:`UtilCallInput`.
        error_message: The message to show when validation fails.
        label: An optional human-readable label for the validator.
        dependencies: Extra port keys to subscribe to, on top of the ones
            inferred from the call.

    Returns:
        ValidatorInput: The validator, with ``dependencies`` filled in.

    Examples:
        ``Annotated[int, withValidator("gt(value, 0)", error_message="Must be positive")]``
    """
    util_call = coerce_util_call(call)
    return ValidatorInput(
        call=util_call,
        source=normalize_expression(call) if isinstance(call, str) else None,
        error_message=error_message,
        label=label,
        dependencies=infer_dependencies(util_call, dependencies),
    )


def withEffect(
    kind: EffectKind,
    call: str | UtilCallInput,
    message: str | None = None,
    dependencies: list[str] | None = None,
) -> EffectInput:
    """Build an effect for a port from a pure blok call.

    The call is evaluated by the UI against its function catalog and must return a
    boolean deciding whether the effect applies. ``value`` refers to the port's own
    value; other names refer to sibling ports and are subscribed to automatically.

    Args:
        kind: The kind of effect (hide, message, ...).
        call: A call expression such as ``"gt(other, 0)"``, or a ready
            :class:`UtilCallInput`.
        message: The message to show if it is a message effect.
        dependencies: Extra port keys to subscribe to, on top of the ones
            inferred from the call.

    Returns:
        EffectInput: The effect, with ``dependencies`` filled in.

    Examples:
        ``Annotated[str, withEffect(EffectKind.HIDE, "gt(other_key, 0)")]``
    """
    util_call = coerce_util_call(call)
    return EffectInput(
        kind=kind,
        call=util_call,
        source=normalize_expression(call) if isinstance(call, str) else None,
        message=message,
        dependencies=infer_dependencies(util_call, dependencies),
    )
