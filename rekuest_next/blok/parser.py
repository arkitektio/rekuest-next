import ast
import uuid
import xml.etree.ElementTree as ET
from typing import Iterable, Optional, Union
from rekuest_next.api.schema import (
    AgentDependencyInput,
    ComponentNodeInput,
    ComponentPropInput,
    DynamicValueInput,
    AgentCallInput,
    UtilCallInput,
    ActionArgumentInput,
    PortMatchInput,
    StateDependencyInput,
    StateImplementationInput,
)
from rekuest_next.definition.match import build_port_matches


class BlokParser:
    """Parses XML/JSX string representations enforcing strict namespace paths and collections."""

    @classmethod
    def parse(cls, jsx_string: str) -> ComponentNodeInput:
        try:
            root_element = ET.fromstring(jsx_string)
            return cls._parse_element(root_element)
        except ET.ParseError as e:
            raise ValueError(cls._format_xml_parse_error(jsx_string, e)) from e

    @staticmethod
    def _format_xml_parse_error(jsx_string: str, error: ET.ParseError) -> str:
        reason = str(error)
        line: int | None = None
        column: int | None = None

        if getattr(error, "position", None) is not None:
            line, column = error.position

        if line is None or column is None:
            return f"Failed to parse JSX/XML: {reason}"

        if ": line " in reason:
            reason = reason.split(": line ", 1)[0]

        headline_reason = reason
        if reason == "no element found":
            headline_reason = (
                "unexpected end of input (no element found). "
                "Check for a missing closing tag before this point"
            )

        source_lines = jsx_string.splitlines()
        if jsx_string.endswith(("\n", "\r")):
            source_lines.append("")

        snippet = ""

        if 1 <= line <= len(source_lines):
            context_before = 2
            context_after = 1
            context_start = max(1, line - context_before)
            context_end = min(len(source_lines), line + context_after)
            context_lines: list[str] = []
            gutter_width = len(str(context_end))

            for snippet_line in range(context_start, context_end + 1):
                source_line = source_lines[snippet_line - 1]
                rendered_line = source_line

                if snippet_line == line and reason == "no element found":
                    if not source_line.strip():
                        rendered_line = f"{' ' * column}<end of input>"

                context_lines.append(
                    f"{snippet_line:>{gutter_width}} | {rendered_line}"
                )

            context_lines.append(f"{' ' * gutter_width} | {' ' * column}^")
            snippet = "\n" + "\n".join(context_lines)

        return (
            f"Failed to parse JSX/XML at line {line}, column {column + 1}: {headline_reason}"
            f"{snippet}"
        )

    @classmethod
    def _parse_element(cls, elem: ET.Element) -> ComponentNodeInput:
        node_id = elem.attrib.pop("id", str(uuid.uuid4()))
        component_name = elem.tag

        props = [cls._parse_prop(k, v) for k, v in elem.attrib.items()]
        children = [cls._parse_element(c) for c in elem]

        return ComponentNodeInput(
            id=node_id,
            component=component_name,
            props=props if props else None,
            children=children if children else None,
        )

    @classmethod
    def _parse_prop(cls, key: str, value: str) -> ComponentPropInput:
        value = value.strip()

        # 1. Top-Level Dynamic Value Binding ($)
        if value.startswith("$"):
            path = value[1:]
            path_parts = path.split(".")
            if len(path_parts) < 3 or path_parts[0] != "state":
                raise ValueError(
                    f"Invalid state namespace for dynamic value prop '{key}': '{path}'. "
                    f"Expected format: state.dependency_key.nested_path"
                )
            return ComponentPropInput(
                key=key, dynamic_value=DynamicValueInput(path=path)
            )

        # 2. Agent/Util Action Callback using AST (@)
        elif value.startswith("@"):
            python_expr = value[1:]
            try:
                tree = ast.parse(python_expr, mode="eval")
                if isinstance(tree.body, (ast.Name, ast.Attribute)):
                    return ComponentPropInput(
                        key=key,
                        dynamic_value=DynamicValueInput(
                            path=cls._extract_path(tree.body)
                        ),
                    )

                if not isinstance(tree.body, ast.Call):
                    raise ValueError(
                        f"Dynamic expression must be a path or function call. Got: {python_expr}"
                    )

                parsed_call = cls._parse_ast_call(tree.body)

                if isinstance(parsed_call, AgentCallInput):
                    return ComponentPropInput(key=key, agent_call=parsed_call)
                else:
                    return ComponentPropInput(key=key, util_call=parsed_call)

            except SyntaxError as e:
                raise ValueError(f"Failed to parse action syntax '{python_expr}': {e}")

        # 3. Static Value
        else:
            declared_value = cls._extract_declared_value(value)
            if declared_value is not None:
                return ComponentPropInput(
                    key=key,
                    static_value=declared_value,
                    declares_value=declared_value,
                )

            return ComponentPropInput(key=key, static_value=value)

    @classmethod
    def _parse_ast_call(cls, node: ast.Call) -> Union[AgentCallInput, UtilCallInput]:
        full_path = cls._extract_path(node.func)
        path_parts = full_path.split(".")

        # --- Process Arguments First ---
        arguments = []
        for arg_node in node.args:
            arguments.append(cls._parse_ast_argument_value(arg_node, key=None))
        for kw in node.keywords:
            arguments.append(cls._parse_ast_argument_value(kw.value, key=kw.arg))

        # --- Enforce Namespaces and Route to Correct Model ---
        if path_parts[0] == "utils":
            if len(path_parts) < 2:
                raise ValueError(f"Invalid utils namespace: '{full_path}'.")

            return UtilCallInput(
                operation=".".join(path_parts[1:]),
                arguments=arguments if arguments else None,
            )

        if path_parts[0] == "actions":
            if len(path_parts) < 3:
                raise ValueError(
                    f"Invalid action namespace: '{full_path}'. Expected: actions.dependency.operation"
                )

            return AgentCallInput(
                dependency=path_parts[1],
                operation=".".join(path_parts[2:]),
                arguments=arguments if arguments else None,
            )

        if len(path_parts) < 2:
            raise ValueError(
                f"Action calls must begin with a dependency key or 'utils.'. Got: '{full_path}'"
            )

        return AgentCallInput(
            dependency=path_parts[0],
            operation=".".join(path_parts[1:]),
            arguments=arguments if arguments else None,
        )

    @classmethod
    def _parse_ast_argument_value(
        cls, node: ast.AST, key: Optional[str] = None
    ) -> ActionArgumentInput:
        """Recursively parses AST nodes into ActionArgumentInput models."""

        # Literal Values (Strings, Ints, Floats, Bools)
        if isinstance(node, ast.Constant):
            return ActionArgumentInput(key=key, value_literal=node.value)

        # State Paths
        elif isinstance(node, (ast.Name, ast.Attribute)):
            path = cls._extract_path(node)
            return ActionArgumentInput(key=key, value_path=path)

        # Nested Action or Util Calls
        elif isinstance(node, ast.Call):
            parsed_call = cls._parse_ast_call(node)
            if isinstance(parsed_call, AgentCallInput):
                return ActionArgumentInput(key=key, agent_call=parsed_call)
            else:
                return ActionArgumentInput(key=key, util_call=parsed_call)

        # Lists and Tuples
        elif isinstance(node, (ast.List, ast.Tuple)):
            parsed_elements = [
                cls._parse_ast_argument_value(elt, key=None) for elt in node.elts
            ]
            return ActionArgumentInput(key=key, value_list=parsed_elements)

        # Dictionaries -> GraphQL Key/Value Arrays
        elif isinstance(node, ast.Dict):
            parsed_dict_list = []
            for k_node, v_node in zip(node.keys, node.values):
                if not isinstance(k_node, ast.Constant) or not isinstance(
                    k_node.value, str
                ):
                    raise ValueError("Dictionary keys must be literal strings.")
                parsed_dict_list.append(
                    cls._parse_ast_argument_value(v_node, key=k_node.value)
                )
            return ActionArgumentInput(key=key, value_dict=parsed_dict_list)

        else:
            raise ValueError(
                f"Unsupported AST node type for argument '{key or 'item'}': {type(node).__name__}"
            )

    @classmethod
    def _extract_path(cls, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{cls._extract_path(node.value)}.{node.attr}"
        raise ValueError(f"Cannot extract path from node type: {type(node).__name__}")

    @staticmethod
    def _extract_declared_value(value: str) -> str | None:
        if not value.startswith("#"):
            return None

        declared_value = value[1:]
        if not declared_value or not declared_value.isidentifier():
            return None

        return declared_value


def validate_blok(
    component: ComponentNodeInput, dependencies: list[AgentDependencyInput]
) -> bool:
    dependency_keys = {dependency.key for dependency in dependencies}
    dependency_aliases = {
        dependency.app: dependency.key
        for dependency in dependencies
        if dependency.app is not None
    }
    dependency_state_demands = {
        dependency.key: {
            state_demand.key: state_demand
            for state_demand in dependency.state_demands or ()
        }
        for dependency in dependencies
    }
    state_demand_index: dict[str, list[tuple[str, StateDependencyInput]]] = {}
    for dependency in dependencies:
        for state_demand in dependency.state_demands or ():
            state_demand_index.setdefault(state_demand.key, []).append(
                (dependency.key, state_demand)
            )

    local_values: dict[str, PortMatchInput | None] = {}
    _validate_node(
        component,
        dependency_keys,
        dependency_aliases,
        dependency_state_demands,
        state_demand_index,
        local_values,
    )
    return True


def _validate_node(
    node: ComponentNodeInput,
    dependency_keys: set[str],
    dependency_aliases: dict[str, str],
    dependency_state_demands: dict[str, dict[str, StateDependencyInput]],
    state_demand_index: dict[str, list[tuple[str, StateDependencyInput]]],
    inherited_locals: dict[str, PortMatchInput | None],
) -> None:
    available_locals = dict(inherited_locals)

    for prop in node.props or ():
        if prop.declares_value:
            available_locals.setdefault(prop.declares_value, None)

    _register_foreach_locals(
        node,
        dependency_aliases,
        dependency_state_demands,
        state_demand_index,
        available_locals,
    )

    for prop in node.props or ():
        _validate_prop(
            prop,
            dependency_keys,
            dependency_aliases,
            dependency_state_demands,
            state_demand_index,
            available_locals,
        )

    for child in node.children or ():
        _validate_node(
            child,
            dependency_keys,
            dependency_aliases,
            dependency_state_demands,
            state_demand_index,
            available_locals,
        )


def _register_foreach_locals(
    node: ComponentNodeInput,
    dependency_aliases: dict[str, str],
    dependency_state_demands: dict[str, dict[str, StateDependencyInput]],
    state_demand_index: dict[str, list[tuple[str, StateDependencyInput]]],
    available_locals: dict[str, PortMatchInput | None],
) -> None:
    if node.component.lower() != "foreach":
        return

    let_prop = next(
        (
            prop
            for prop in node.props or ()
            if prop.key == "let" and prop.declares_value
        ),
        None,
    )
    items_prop = next(
        (
            prop
            for prop in node.props or ()
            if prop.key == "items"
            and prop.dynamic_value is not None
            and prop.dynamic_value.path is not None
        ),
        None,
    )

    if let_prop is None or items_prop is None or items_prop.dynamic_value is None:
        return

    resolved_match = _resolve_path_match(
        items_prop.dynamic_value.path,
        dependency_aliases,
        dependency_state_demands,
        state_demand_index,
        available_locals,
        context=f"prop '{items_prop.key}'",
    )
    available_locals[let_prop.declares_value] = _infer_iterable_item_match(
        resolved_match,
        items_prop.dynamic_value.path,
    )


def _validate_prop(
    prop: ComponentPropInput,
    dependency_keys: set[str],
    dependency_aliases: dict[str, str],
    dependency_state_demands: dict[str, dict[str, StateDependencyInput]],
    state_demand_index: dict[str, list[tuple[str, StateDependencyInput]]],
    available_locals: dict[str, PortMatchInput | None],
) -> None:
    if prop.dynamic_value is not None and prop.dynamic_value.path is not None:
        _validate_path(
            prop.dynamic_value.path,
            dependency_keys,
            dependency_aliases,
            dependency_state_demands,
            state_demand_index,
            available_locals,
            context=f"prop '{prop.key}'",
        )

    if prop.agent_call is not None:
        _validate_agent_call(
            prop.agent_call,
            dependency_keys,
            dependency_aliases,
            dependency_state_demands,
            state_demand_index,
            available_locals,
        )

    if prop.util_call is not None:
        _validate_util_call(
            prop.util_call,
            dependency_keys,
            dependency_aliases,
            dependency_state_demands,
            state_demand_index,
            available_locals,
        )


def _validate_agent_call(
    agent_call: AgentCallInput,
    dependency_keys: set[str],
    dependency_aliases: dict[str, str],
    dependency_state_demands: dict[str, dict[str, StateDependencyInput]],
    state_demand_index: dict[str, list[tuple[str, StateDependencyInput]]],
    available_locals: dict[str, PortMatchInput | None],
) -> None:
    canonical_dependency = dependency_aliases.get(
        agent_call.dependency, agent_call.dependency
    )
    if canonical_dependency not in dependency_keys:
        raise ValueError(
            f"Unknown dependency '{agent_call.dependency}' in agent call. "
            f"Available dependencies: {sorted(dependency_keys | set(dependency_aliases))}"
        )

    for argument in agent_call.arguments or ():
        _validate_argument(
            argument,
            dependency_keys,
            dependency_aliases,
            dependency_state_demands,
            state_demand_index,
            available_locals,
        )


def _validate_util_call(
    util_call: UtilCallInput,
    dependency_keys: set[str],
    dependency_aliases: dict[str, str],
    dependency_state_demands: dict[str, dict[str, StateDependencyInput]],
    state_demand_index: dict[str, list[tuple[str, StateDependencyInput]]],
    available_locals: dict[str, PortMatchInput | None],
) -> None:
    for argument in util_call.arguments or ():
        _validate_argument(
            argument,
            dependency_keys,
            dependency_aliases,
            dependency_state_demands,
            state_demand_index,
            available_locals,
        )


def _validate_argument(
    argument: ActionArgumentInput,
    dependency_keys: set[str],
    dependency_aliases: dict[str, str],
    dependency_state_demands: dict[str, dict[str, StateDependencyInput]],
    state_demand_index: dict[str, list[tuple[str, StateDependencyInput]]],
    available_locals: dict[str, PortMatchInput | None],
) -> None:
    if argument.value_path is not None:
        _validate_path(
            argument.value_path,
            dependency_keys,
            dependency_aliases,
            dependency_state_demands,
            state_demand_index,
            available_locals,
            context=f"argument '{argument.key or 'positional'}'",
        )

    if argument.agent_call is not None:
        _validate_agent_call(
            argument.agent_call,
            dependency_keys,
            dependency_aliases,
            dependency_state_demands,
            state_demand_index,
            available_locals,
        )

    if argument.util_call is not None:
        _validate_util_call(
            argument.util_call,
            dependency_keys,
            dependency_aliases,
            dependency_state_demands,
            state_demand_index,
            available_locals,
        )

    for nested_argument in argument.value_list or ():
        _validate_argument(
            nested_argument,
            dependency_keys,
            dependency_aliases,
            dependency_state_demands,
            state_demand_index,
            available_locals,
        )

    for nested_argument in argument.value_dict or ():
        _validate_argument(
            nested_argument,
            dependency_keys,
            dependency_aliases,
            dependency_state_demands,
            state_demand_index,
            available_locals,
        )


def _validate_path(
    path: str,
    dependency_keys: set[str],
    dependency_aliases: dict[str, str],
    dependency_state_demands: dict[str, dict[str, StateDependencyInput]],
    state_demand_index: dict[str, list[tuple[str, StateDependencyInput]]],
    available_locals: dict[str, PortMatchInput | None],
    context: str,
) -> None:
    _resolve_path_match(
        path,
        dependency_aliases,
        dependency_state_demands,
        state_demand_index,
        available_locals,
        context,
        dependency_keys=dependency_keys,
    )


def _resolve_path_match(
    path: str,
    dependency_aliases: dict[str, str],
    dependency_state_demands: dict[str, dict[str, StateDependencyInput]],
    state_demand_index: dict[str, list[tuple[str, StateDependencyInput]]],
    available_locals: dict[str, PortMatchInput | None],
    context: str,
    dependency_keys: set[str] | None = None,
) -> PortMatchInput | None:
    path_parts = path.split(".")
    root = path_parts[0]
    dependency_keys = dependency_keys or set(dependency_state_demands)

    if root in available_locals:
        return _resolve_port_match_path(
            available_locals[root],
            path_parts[1:],
            path,
            context,
        )

    canonical_root = dependency_aliases.get(root, root)

    if canonical_root in dependency_state_demands:
        return _resolve_dependency_state_path(
            canonical_root,
            path_parts[1:],
            dependency_state_demands,
            path,
            context,
        )

    if root == "state":
        canonical_state_dependency = dependency_aliases.get(
            path_parts[1], path_parts[1]
        )
        if (
            len(path_parts) > 2
            and canonical_state_dependency in dependency_state_demands
        ):
            return _resolve_dependency_state_path(
                canonical_state_dependency,
                path_parts[2:],
                dependency_state_demands,
                path,
                context,
            )

        if len(path_parts) > 1:
            state_key = path_parts[1]
            matching_state_demands = state_demand_index.get(state_key, [])
            if len(matching_state_demands) == 1:
                _, state_demand = matching_state_demands[0]
                return _resolve_port_match_path(
                    _state_demand_root_match(state_demand),
                    path_parts[2:],
                    path,
                    context,
                )
            if len(matching_state_demands) > 1:
                raise ValueError(
                    f"Ambiguous state reference '{path}' in {context}. "
                    f"State '{state_key}' exists on multiple dependencies. "
                    f"Use 'state.<dependency>.{state_key}...' or '<dependency>.{state_key}...'."
                )

    if root == "actions" and len(path_parts) > 1:
        canonical_action_dependency = dependency_aliases.get(
            path_parts[1], path_parts[1]
        )
        if canonical_action_dependency in dependency_keys:
            return None

    if canonical_root in dependency_keys:
        return None

    if root == "utils":
        return None

    state_keys = sorted(state_demand_index)
    raise ValueError(
        f"Unknown non-static reference '{path}' in {context}. "
        f"Available locals: {sorted(available_locals)}. "
        f"Available dependencies: {sorted(dependency_keys)}. "
        f"Available state values: {state_keys}"
    )


def _resolve_dependency_state_path(
    dependency_key: str,
    path_parts: list[str],
    dependency_state_demands: dict[str, dict[str, StateDependencyInput]],
    path: str,
    context: str,
) -> PortMatchInput | None:
    if not path_parts:
        return None

    state_key = path_parts[0]
    state_demand = dependency_state_demands.get(dependency_key, {}).get(state_key)
    if state_demand is None:
        available_state_keys = sorted(dependency_state_demands.get(dependency_key, {}))
        raise ValueError(
            f"Unknown nested reference '{path}' in {context}: state '{state_key}' "
            f"does not exist on dependency '{dependency_key}'. "
            f"Available states: {available_state_keys}"
        )

    return _resolve_port_match_path(
        _state_demand_root_match(state_demand),
        path_parts[1:],
        path,
        context,
    )


def _state_demand_root_match(state_demand: StateDependencyInput) -> PortMatchInput:
    return PortMatchInput(
        key=state_demand.key,
        children=state_demand.port_matches,
    )


def _resolve_port_match_path(
    port_match: PortMatchInput | None,
    path_parts: list[str],
    path: str,
    context: str,
) -> PortMatchInput | None:
    current_match = port_match
    remaining_parts = list(path_parts)

    if current_match is None:
        if remaining_parts:
            raise ValueError(
                f"Unknown nested reference '{path}' in {context}: no schema is available "
                f"to validate '{remaining_parts[0]}'"
            )
        return None

    while remaining_parts:
        next_part = remaining_parts.pop(0)
        children = current_match.children or ()

        if not children:
            raise ValueError(
                f"Unknown nested reference '{path}' in {context}: '{next_part}' does not exist"
            )

        child_match = next(
            (child for child in children if child.key == next_part), None
        )
        if child_match is None and len(children) == 1 and children[0].key == "...":
            child_match = children[0]

        if child_match is None:
            available_keys = sorted(
                child.key
                for child in children
                if child.key is not None and child.key != "..."
            )
            raise ValueError(
                f"Unknown nested reference '{path}' in {context}: '{next_part}' does not exist. "
                f"Available keys: {available_keys}"
            )

        current_match = child_match

    return current_match


def _infer_iterable_item_match(
    port_match: PortMatchInput | None,
    path: str,
) -> PortMatchInput | None:
    if port_match is None:
        return None

    children = port_match.children or ()
    if len(children) == 1 and children[0].key == "...":
        return children[0]

    raise ValueError(
        f"ForEach items reference '{path}' must resolve to a list-like value"
    )


def resolve_state_reference(
    dependency: Optional[str],
    state_path: str,
    *,
    dependencies: Iterable[AgentDependencyInput],
    own_states: Iterable[StateImplementationInput],
    context: str,
) -> None:
    """Validate a ``withStateChoices`` state reference is resolvable.

    A ``dependency`` of ``None`` denotes a ``self`` reference which is resolved
    against the agent's own ``own_states``. A named ``dependency`` is resolved
    through that dependency's declared ``state_demands``.

    Raises:
        ValueError: If the reference cannot be resolved.
    """
    path_parts = [part for part in state_path.split(".") if part]
    if not path_parts:
        return

    if dependency is None:
        own_by_interface = {state.interface: state for state in own_states}
        state_key = path_parts[0]
        state = own_by_interface.get(state_key)
        if state is None:
            raise ValueError(
                f"Unknown self state reference '{state_path}' in {context}: "
                f"no own state '{state_key}'. "
                f"Available states: {sorted(own_by_interface)}"
            )
        root_match = PortMatchInput(
            key=state_key,
            children=build_port_matches(state.definition.ports),
        )
        _resolve_port_match_path(root_match, path_parts[1:], state_path, context)
        return

    dependency_state_demands = {
        dep.key: {
            state_demand.key: state_demand for state_demand in dep.state_demands or ()
        }
        for dep in dependencies
    }
    if dependency not in dependency_state_demands:
        raise ValueError(
            f"State choice widget in {context} references unknown dependency "
            f"'{dependency}'. Available dependencies: {sorted(dependency_state_demands)}"
        )

    _resolve_dependency_state_path(
        dependency,
        path_parts,
        dependency_state_demands,
        state_path,
        context,
    )


# ============================================================================
# 3. Example Execution
# ============================================================================


def jsx(string: str) -> ComponentNodeInput:
    """Parse a JSX/XML blok string into a component tree.

    The helper delegates to :class:`BlokParser` and raises a formatted
    :class:`ValueError` when XML parsing fails. Error messages include line and
    column information plus nearby source context.

    Args:
        string: JSX-like XML source describing a blok component tree.

    Returns:
        Parsed component tree as a :class:`ComponentNodeInput`.

    Raises:
        ValueError: If the XML cannot be parsed or validated.

    Examples:
        Parse a minimal blok layout::

            component = jsx("<Page><Label text=\"Ready\" /></Page>")
    """
    return BlokParser.parse(string)
