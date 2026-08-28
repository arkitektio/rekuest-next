import ast
import xml.etree.ElementTree as ET

from rekuest_next.api.schema import (
    ActionArgumentInput,
    AgentProbeInput,
    ComponentNodeInput,
    ComponentPropInput,
    DynamicValueInput,
    UtilProbeInput,
)
from rekuest_next.blok.walk import FOREACH_COMPONENT, FOREACH_LET_PROP


class BlokParser:
    """Parses XML/JSX string representations enforcing strict namespace paths and collections."""

    @classmethod
    def parse(cls, jsx_string: str) -> ComponentNodeInput:
        try:
            root_element = ET.fromstring(jsx_string)
        except ET.ParseError as e:
            raise ValueError(cls._format_xml_parse_error(jsx_string, e)) from e
        return cls._parse_element(root_element, root_element.tag)

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
    def _parse_element(cls, elem: ET.Element, path: str) -> ComponentNodeInput:
        # Copy rather than pop from elem.attrib: mutating the ElementTree would
        # make a second parse of the same tree behave differently.
        attributes = dict(elem.attrib)
        node_id = attributes.pop("id", None) or path

        cls._reject_element_text(elem, node_id)

        props = [cls._parse_prop(elem.tag, key, value) for key, value in attributes.items()]

        children: list[ComponentNodeInput] = []
        seen_tags: dict[str, int] = {}
        for child in elem:
            index = seen_tags.get(child.tag, 0)
            seen_tags[child.tag] = index + 1
            children.append(cls._parse_element(child, f"{node_id}/{child.tag}[{index}]"))

        return ComponentNodeInput(
            id=node_id,
            component=elem.tag,
            props=props if props else None,
            children=children if children else None,
        )

    @staticmethod
    def _reject_element_text(elem: ET.Element, node_id: str) -> None:
        """Reject inner text, which the renderer never sees.

        Components take their content as a prop (``text="..."``). Silently
        dropping ``<Badge>hello</Badge>`` loses the message with no diagnostic,
        so refuse it instead.
        """

        def fail(text: str) -> None:
            raise ValueError(
                f"Text content is not rendered in <{elem.tag}> ({node_id}): "
                f"{text.strip()!r}. Pass it as a prop instead, e.g. "
                f'<{elem.tag} text="{text.strip()}" />'
            )

        if elem.text and elem.text.strip():
            fail(elem.text)

        for child in elem:
            if child.tail and child.tail.strip():
                fail(child.tail)

    @classmethod
    def _parse_prop(cls, component: str, key: str, value: str) -> ComponentPropInput:
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

                if isinstance(parsed_call, AgentProbeInput):
                    return ComponentPropInput(key=key, agent_call=parsed_call)
                else:
                    return ComponentPropInput(key=key, util_call=parsed_call)

            except SyntaxError as e:
                raise ValueError(f"Failed to parse action syntax '{python_expr}': {e}")

        # 3. A foreach loop variable declaration (#name)
        elif cls._is_foreach_let(component, key):
            return cls._parse_foreach_let(component, key, value)

        # 4. Static Value
        else:
            return ComponentPropInput(key=key, static_value=value)

    @staticmethod
    def _is_foreach_let(component: str, key: str) -> bool:
        """Whether this prop is the loop variable of a ``foreach``.

        ``#name`` declares a local *only here*. Honouring it on every prop made
        ordinary values such as ``color="#fff"`` silently lose their leading
        ``#`` and declare a phantom local named ``fff``.
        """
        return component.lower() == FOREACH_COMPONENT and key == FOREACH_LET_PROP

    @staticmethod
    def _parse_foreach_let(component: str, key: str, value: str) -> ComponentPropInput:
        declared_value = value[1:] if value.startswith("#") else ""
        if not declared_value or not declared_value.isidentifier():
            raise ValueError(
                f"<{component}> prop '{key}' must declare a loop variable as "
                f"'#name', where name is a valid identifier. Got: {value!r}"
            )
        return ComponentPropInput(
            key=key,
            static_value=declared_value,
            declares_value=declared_value,
        )

    @classmethod
    def _parse_ast_call(cls, node: ast.Call) -> AgentProbeInput | UtilProbeInput:
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

            return UtilProbeInput(
                operation=".".join(path_parts[1:]),
                arguments=arguments if arguments else None,
            )

        if path_parts[0] == "actions":
            if len(path_parts) < 3:
                raise ValueError(
                    f"Invalid action namespace: '{full_path}'. Expected: actions.dependency.operation"
                )

            return AgentProbeInput(
                dependency=path_parts[1],
                operation=".".join(path_parts[2:]),
                arguments=arguments if arguments else None,
            )

        if len(path_parts) < 2:
            raise ValueError(
                f"Action calls must begin with a dependency key or 'utils.'. Got: '{full_path}'"
            )

        return AgentProbeInput(
            dependency=path_parts[0],
            operation=".".join(path_parts[1:]),
            arguments=arguments if arguments else None,
        )

    @classmethod
    def _parse_ast_argument_value(
        cls, node: ast.AST, key: str | None = None
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
            if isinstance(parsed_call, AgentProbeInput):
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



def jsx(string: str) -> ComponentNodeInput:
    """Parse a JSX/XML blok string into a component tree.

    The helper delegates to :class:`BlokParser` and raises a formatted
    :class:`ValueError` when XML parsing fails. Error messages include line and
    column information plus nearby source context.

    Node ids are structural (``Card/CardContent[0]/Button[1]``) unless the
    element carries an explicit ``id``, so parsing the same source twice yields
    an identical tree.

    Args:
        string: JSX-like XML source describing a blok component tree.

    Returns:
        Parsed component tree as a :class:`ComponentNodeInput`.

    Raises:
        ValueError: If the XML cannot be parsed or validated.

    Examples:
        Parse a minimal blok layout::

            component = jsx('<Page><Label text="Ready" /></Page>')
    """
    return BlokParser.parse(string)
