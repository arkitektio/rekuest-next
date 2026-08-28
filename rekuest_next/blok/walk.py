"""Shared traversal for blok component trees.

Validation (:mod:`rekuest_next.blok.parser`) and dependency inference
(:mod:`rekuest_next.blok.registry`) walk the same ``ComponentNodeInput`` shape --
props, agent/util calls, nested arguments -- under the same ``foreach`` scoping
rules. Two hand-written walkers drifted once already (``foreach`` item inference
only ever landed in the parser), so the traversal lives here and the callers
supply a visitor.
"""

from typing import Any, Protocol

from rekuest_next.api.schema import (
    ActionArgumentInput,
    AgentProbeInput,
    ComponentNodeInput,
    ComponentPropInput,
    UtilProbeInput,
)

FOREACH_COMPONENT = "foreach"
FOREACH_LET_PROP = "let"
FOREACH_ITEMS_PROP = "items"


class BlokVisitor(Protocol):
    """Callbacks invoked by :func:`walk_component`.

    ``scope`` maps a local name declared by an enclosing ``foreach`` to whatever
    :meth:`declare_foreach_local` returned for it. ``context`` is a human-readable
    location (``"prop 'text' of <Button> (Card/Button[0])"``) for error messages.
    """

    def visit_path(
        self, path: str, scope: dict[str, Any], context: str
    ) -> None:  # pragma: no cover - protocol
        ...

    def visit_agent_call(
        self, call: AgentProbeInput, scope: dict[str, Any], context: str
    ) -> None:  # pragma: no cover - protocol
        ...

    def visit_util_call(
        self, call: UtilProbeInput, scope: dict[str, Any], context: str
    ) -> None:  # pragma: no cover - protocol
        ...

    def declare_foreach_local(
        self, name: str, items_path: str, scope: dict[str, Any], context: str
    ) -> Any:  # pragma: no cover - protocol
        ...


def action_key_for(call: AgentProbeInput) -> str:
    """The action key an agent call names.

    An operation may be dotted (``dep.a.b``); the action itself is the last
    segment, since ``AppRegistry.implementations`` is keyed by bare interface.
    Both the validator and the dependency collector resolve operations through
    here so they cannot disagree about what an action is called.
    """
    return call.operation.split(".")[-1]


def node_context(node: ComponentNodeInput) -> str:
    """Render a node as ``<Component> (structural/id)`` for error messages."""
    return f"<{node.component}> ({node.id})"


def prop_context(node: ComponentNodeInput, prop: ComponentPropInput) -> str:
    """Render a prop location for error messages."""
    return f"prop '{prop.key}' of {node_context(node)}"


def foreach_parts(
    node: ComponentNodeInput,
) -> tuple[str | None, str | None]:
    """Return ``(let_name, items_path)`` for a ``foreach`` node, else ``(None, None)``."""
    if node.component.lower() != FOREACH_COMPONENT:
        return None, None

    let_name = next(
        (
            prop.declares_value
            for prop in node.props or ()
            if prop.key == FOREACH_LET_PROP and prop.declares_value
        ),
        None,
    )
    items_path = next(
        (
            prop.dynamic_value.path
            for prop in node.props or ()
            if prop.key == FOREACH_ITEMS_PROP
            and prop.dynamic_value is not None
            and prop.dynamic_value.path is not None
        ),
        None,
    )
    return let_name, items_path


def walk_component(
    node: ComponentNodeInput,
    visitor: BlokVisitor,
    scope: dict[str, Any] | None = None,
) -> None:
    """Walk ``node`` and its subtree, invoking ``visitor`` for every reference."""
    current_scope = dict(scope or {})

    binding = _declare_foreach(node, visitor, current_scope)
    if binding is not None:
        let_name, value = binding
        current_scope[let_name] = value

    for prop in node.props or ():
        _walk_prop(node, prop, visitor, current_scope)

    for child in node.children or ():
        walk_component(child, visitor, current_scope)


def _declare_foreach(
    node: ComponentNodeInput, visitor: BlokVisitor, scope: dict[str, Any]
) -> tuple[str, Any] | None:
    """Return the ``(name, value)`` a ``foreach`` node binds, or ``None``.

    ``scope`` is read-only here: the caller owns the binding so scope mutation
    happens in exactly one place (:func:`walk_component`).
    """
    if node.component.lower() != FOREACH_COMPONENT:
        return None

    let_name, items_path = foreach_parts(node)
    if let_name is None or items_path is None:
        missing = [
            name
            for name, value in (
                (FOREACH_LET_PROP, let_name),
                (FOREACH_ITEMS_PROP, items_path),
            )
            if value is None
        ]
        raise ValueError(
            f"{node_context(node)} is missing required prop(s) {missing}. A "
            f"{FOREACH_COMPONENT} needs {FOREACH_ITEMS_PROP}=\"@<path>\" and "
            f"{FOREACH_LET_PROP}=\"#<name>\"."
        )

    # The items path is resolved in the *enclosing* scope: a foreach cannot
    # iterate over the variable it is about to declare.
    return let_name, visitor.declare_foreach_local(
        let_name,
        items_path,
        scope,
        f"prop '{FOREACH_ITEMS_PROP}' of {node_context(node)}",
    )


def _walk_prop(
    node: ComponentNodeInput,
    prop: ComponentPropInput,
    visitor: BlokVisitor,
    scope: dict[str, Any],
) -> None:
    context = prop_context(node, prop)

    if prop.dynamic_value is not None and prop.dynamic_value.path is not None:
        visitor.visit_path(prop.dynamic_value.path, scope, context)

    if prop.agent_call is not None:
        _walk_agent_call(prop.agent_call, visitor, scope, context)

    if prop.util_call is not None:
        _walk_util_call(prop.util_call, visitor, scope, context)


def _walk_agent_call(
    call: AgentProbeInput, visitor: BlokVisitor, scope: dict[str, Any], context: str
) -> None:
    visitor.visit_agent_call(call, scope, context)
    for argument in call.arguments or ():
        _walk_argument(argument, visitor, scope, context)


def _walk_util_call(
    call: UtilProbeInput, visitor: BlokVisitor, scope: dict[str, Any], context: str
) -> None:
    visitor.visit_util_call(call, scope, context)
    for argument in call.arguments or ():
        _walk_argument(argument, visitor, scope, context)


def _walk_argument(
    argument: ActionArgumentInput,
    visitor: BlokVisitor,
    scope: dict[str, Any],
    context: str,
) -> None:
    nested_context = f"argument '{argument.key or 'positional'}' of {context}"

    if argument.value_path is not None:
        visitor.visit_path(argument.value_path, scope, nested_context)

    if argument.agent_call is not None:
        _walk_agent_call(argument.agent_call, visitor, scope, nested_context)

    if argument.util_call is not None:
        _walk_util_call(argument.util_call, visitor, scope, nested_context)

    for nested in argument.value_list or ():
        _walk_argument(nested, visitor, scope, nested_context)

    for nested in argument.value_dict or ():
        _walk_argument(nested, visitor, scope, nested_context)
