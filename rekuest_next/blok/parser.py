import ast
import functools
import io
import keyword
import tokenize
import xml.etree.ElementTree as ET

from rekuest_next.api.schema import (
    ActionArgumentInput,
    AgentProbeInput,
    ComponentNodeInput,
    ComponentPropInput,
    DynamicValueInput,
    UtilCallInput,
)
from rekuest_next.blok.walk import FOREACH_COMPONENT, FOREACH_LET_PROP
from rekuest_next.traits.calls import resolve_base_arguments


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
    def _parse_ast_call(cls, node: ast.Call) -> AgentProbeInput | UtilCallInput:
        full_path = cls._extract_path(node.func)
        path_parts = full_path.split(".")

        # --- Process Arguments First ---
        arguments = cls._parse_call_arguments(node)

        # --- Enforce Namespaces and Route to Correct Model ---
        if path_parts[0] == "utils":
            if len(path_parts) < 2:
                raise ValueError(f"Invalid utils namespace: '{full_path}'.")

            operation = ".".join(path_parts[1:])
            arguments = resolve_base_arguments(operation, arguments, f"utils.{operation}")
            return UtilCallInput(
                operation=operation,
                arguments=tuple(arguments) if arguments else None,
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
    def _parse_call_arguments(cls, node: ast.Call) -> list[ActionArgumentInput]:
        """Parse a call's arguments into keyed entries.

        Call arguments are a map on the wire: positional arguments are keyed by
        their index (``"0"``, ``"1"``, ...; the UI maps them onto the operation's
        parameters in order) and keyword arguments by name.
        """
        arguments = [
            cls._parse_ast_argument_value(arg_node, key=str(index))
            for index, arg_node in enumerate(node.args)
        ]
        for kw in node.keywords:
            if kw.arg is None:
                raise ValueError("Call arguments cannot be unpacked with '**'")
            arguments.append(cls._parse_ast_argument_value(kw.value, key=kw.arg))
        return arguments

    @classmethod
    def _parse_ast_argument_value(
        cls, node: ast.AST, key: str | None = None
    ) -> ActionArgumentInput:
        """Recursively parses AST nodes into ActionArgumentInput models."""

        # Literal Values (Strings, Ints, Floats, Bools)
        if isinstance(node, ast.Constant):
            if node.value is None:
                raise ValueError(
                    f"Argument '{key or 'item'}' cannot be None: a missing literal is "
                    "indistinguishable from no value. Omit the argument instead."
                )
            return ActionArgumentInput(key=key, value_literal=node.value)

        # Signed numeric literals (-1, +2.5)
        elif (
            isinstance(node, ast.UnaryOp)
            and isinstance(node.op, (ast.USub, ast.UAdd))
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, (int, float))
            and not isinstance(node.operand.value, bool)
        ):
            value = node.operand.value
            if isinstance(node.op, ast.USub):
                value = -value
            return ActionArgumentInput(key=key, value_literal=value)

        # State Paths
        elif isinstance(node, (ast.Name, ast.Attribute)):
            path = cls._argument_path(node)
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
                if (
                    not isinstance(k_node, ast.Constant)
                    or not isinstance(k_node.value, str)
                    or not k_node.value
                ):
                    raise ValueError("Dictionary keys must be non-empty literal strings.")
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

    @classmethod
    def _argument_path(cls, node: ast.AST) -> str:
        """Render a ``Name``/``Attribute`` argument as a ``value_path``.

        Blok props keep dotted state paths; subclasses may choose another form.
        """
        return cls._extract_path(node)


class PortCallParser(BlokParser):
    """Parses a pure port-call expression such as ``value > 3`` or ``gt(value, other.min)``.

    Port validators and effects carry a :class:`UtilCallInput` that the UI evaluates
    against its catalog. The expression is a Python expression subset:

    - a call whose callee is the operation (``gt``, ``math.multiply``); a leading
      ``utils.`` or ``@`` is tolerated and stripped,
    - operator sugar desugared onto base-catalog operations: comparisons
      (``> >= < <= == !=`` -> ``gt gte lt lte eq ne``, chains fold with ``and``),
      ``and``/``or``/``not``, ``in``/``not in``, ``is None``/``is not None``
      (``is_null``/``is_set``), ``x if c else y`` (``if``) and arithmetic
      (``+ - * / %`` -> ``add sub mul div mod``, unary minus -> ``neg``; ``//`` and ``**``
      are not supported),
    - bare names, attribute chains and subscripts are value paths (``value`` is the
      port's own value, ``other.min`` / ``other["min"]`` the field ``min`` inside the
      value of port ``other``), emitted JSON-pointer style (``other/min``),
    - constants, keyword arguments, nested calls, lists and dicts work as in blok
      props. Positional arguments of base operations are named after the operation's
      parameters; for other operations they are keyed by index (``"0"``, ``"1"``, ...),
      which the UI maps onto parameters in order.

    Port calls must be pure: ``actions.*`` callees are rejected and every other callee is
    a catalog operation.
    """

    KEYWORD_PREFIX = "kw__"
    """Prefix used to smuggle Python keywords (``if``, ``and``, ``not``) through ``ast``."""

    _CALLEE_PRECEDERS = frozenset({"(", "[", "{", ",", "=", ":"})

    _ARITHMETIC: dict[type[ast.operator], str] = {
        ast.Add: "add",
        ast.Sub: "sub",
        ast.Mult: "mul",
        ast.Div: "div",
        ast.Mod: "mod",
    }

    _COMPARISONS: dict[type[ast.cmpop], str] = {
        ast.Gt: "gt",
        ast.GtE: "gte",
        ast.Lt: "lt",
        ast.LtE: "lte",
        ast.Eq: "eq",
        ast.NotEq: "ne",
    }

    @classmethod
    def _escape_keyword_names(cls, source: str) -> str:
        """Rename keyword tokens used as callees or attributes so ``ast`` accepts them.

        Catalog operations may be named like Python keywords (``if``, ``and``,
        ``not``). A keyword directly followed by ``(`` or preceded by ``.`` is
        prefixed with :attr:`KEYWORD_PREFIX`; :meth:`_unescape_name` restores it.
        """
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
        except tokenize.TokenError as e:
            raise ValueError(f"Failed to parse port call '{source}': {e}") from e

        skipped = {tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT}
        significant = [tok for tok in tokens if tok.type not in skipped]
        renamed: list[tuple[int, str]] = []
        for index, tok in enumerate(significant):
            string = tok.string
            if tok.type == tokenize.NAME and keyword.iskeyword(string):
                nxt = significant[index + 1] if index + 1 < len(significant) else None
                prev = significant[index - 1] if index > 0 else None
                follows_dot = prev is not None and prev.type == tokenize.OP and prev.string == "."
                precedes_call = nxt is not None and nxt.type == tokenize.OP and nxt.string == "("
                # Only a keyword in *callee* position is an operation name (``if(`` at the start,
                # after ``(``, ``,``, ``=``, ...). ``x and (y)`` or ``not (x)`` are operators and
                # must reach Python's grammar, where the desugarer maps them onto the same names.
                callee_position = prev is None or (
                    prev.type == tokenize.OP and prev.string in cls._CALLEE_PRECEDERS
                )
                if follows_dot or (precedes_call and callee_position):
                    string = cls.KEYWORD_PREFIX + string
            renamed.append((tok.type, string))
        return tokenize.untokenize(renamed)

    @classmethod
    def _unescape_name(cls, path: str, separator: str) -> str:
        prefix = cls.KEYWORD_PREFIX
        return separator.join(
            part[len(prefix) :] if part.startswith(prefix) else part
            for part in path.split(separator)
        )

    @classmethod
    def parse_expression(cls, expression: str) -> UtilCallInput:
        source = expression.strip()
        if source.startswith("@"):
            source = source[1:].lstrip()
        try:
            tree = ast.parse(cls._escape_keyword_names(source), mode="eval")
        except SyntaxError as e:
            raise ValueError(f"Failed to parse port call '{expression}': {e}") from e

        if not cls._is_call_like(tree.body):
            raise ValueError(
                "A port call must be a call or boolean expression like 'gt(value, 3)' or "
                f"'value > 3'. Got: '{expression}'"
            )
        return cls._desugar(tree.body)

    @classmethod
    def _is_call_like(cls, node: ast.AST) -> bool:
        return isinstance(node, (ast.Call, ast.Compare, ast.BoolOp, ast.IfExp, ast.BinOp)) or (
            isinstance(node, ast.UnaryOp) and not cls._is_signed_constant(node)
        )

    @staticmethod
    def _is_signed_constant(node: ast.UnaryOp) -> bool:
        """``-1`` / ``+2.5``: a literal, handled by the base argument parser."""
        return (
            isinstance(node.op, (ast.USub, ast.UAdd))
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, (int, float))
            and not isinstance(node.operand.value, bool)
        )

    @classmethod
    def _desugar(cls, node: ast.AST) -> UtilCallInput:
        """Turn a call or operator expression into a base-catalog call tree."""
        if isinstance(node, ast.Call):
            return cls._parse_ast_call(node)

        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            parts = [
                cls._desugar_comparison(op, left, right)
                for op, left, right in zip(node.ops, operands, operands[1:])
            ]
            return functools.reduce(lambda acc, part: cls._base_call("and", a=acc, b=part), parts)

        if isinstance(node, ast.BoolOp):
            name = "and" if isinstance(node.op, ast.And) else "or"
            return functools.reduce(
                lambda acc, value: cls._base_call(name, a=acc, b=value), node.values
            )

        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                return cls._base_call("not", a=node.operand)
            if isinstance(node.op, ast.USub):
                return cls._base_call("neg", a=node.operand)
            if isinstance(node.op, ast.UAdd):
                if cls._is_call_like(node.operand):
                    return cls._desugar(node.operand)
                raise ValueError("Unary plus on a value is not an expression; write the value itself")
            raise ValueError("Bitwise operators are not supported in port calls")

        if isinstance(node, ast.IfExp):
            return cls._base_call("if", condition=node.test, then=node.body, otherwise=node.orelse)

        if isinstance(node, ast.BinOp):
            name = cls._ARITHMETIC.get(type(node.op))
            if name is None:
                raise ValueError(
                    f"Operator {type(node.op).__name__} is not supported in port calls "
                    "(the base catalog has add, sub, mul, div and mod)"
                )
            return cls._base_call(name, a=node.left, b=node.right)
        raise ValueError(f"Unsupported expression in port call: {type(node).__name__}")

    @classmethod
    def _desugar_comparison(cls, op: ast.cmpop, left: ast.AST, right: ast.AST) -> UtilCallInput:
        if isinstance(op, ast.In):
            return cls._base_call("in", value=left, options=right)
        if isinstance(op, ast.NotIn):
            return cls._base_call("not", a=cls._base_call("in", value=left, options=right))
        if isinstance(op, (ast.Is, ast.IsNot)):
            if not (isinstance(right, ast.Constant) and right.value is None):
                raise ValueError("'is' is only supported as 'is None' / 'is not None'")
            return cls._base_call("is_null" if isinstance(op, ast.Is) else "is_set", a=left)
        name = cls._COMPARISONS.get(type(op))
        if name is None:
            raise ValueError(f"Unsupported comparison in port call: {type(op).__name__}")
        return cls._base_call(name, a=left, b=right)

    @classmethod
    def _base_call(cls, operation: str, **operands: "ast.AST | UtilCallInput") -> UtilCallInput:
        """A base-catalog call with named arguments, from AST nodes or already-built calls."""
        arguments = [
            ActionArgumentInput(key=key, util_call=operand)
            if isinstance(operand, UtilCallInput)
            else cls._parse_ast_argument_value(operand, key=key)
            for key, operand in operands.items()
        ]
        arguments = resolve_base_arguments(operation, arguments, f"{operation}(...)")
        return UtilCallInput(operation=operation, arguments=tuple(arguments))

    @classmethod
    def _parse_ast_argument_value(  # type: ignore[override]
        cls, node: ast.AST, key: str | None = None
    ) -> ActionArgumentInput:
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd) and not cls._is_signed_constant(node):
            return cls._parse_ast_argument_value(node.operand, key)  # ``+x`` is ``x``
        if cls._is_call_like(node) and not isinstance(node, ast.Call):
            return ActionArgumentInput(key=key, util_call=cls._desugar(node))
        if isinstance(node, ast.Subscript):
            return ActionArgumentInput(key=key, value_path=cls._subscript_path(node))
        return super()._parse_ast_argument_value(node, key)

    @classmethod
    def _subscript_path(cls, node: ast.AST) -> str:
        """``other["k"]`` / ``items[0]`` / ``other.list[1].x`` as a JSON-pointer path."""
        segments: list[str] = []
        while isinstance(node, (ast.Subscript, ast.Attribute)):
            if isinstance(node, ast.Attribute):
                segments.insert(0, cls._pointer_segment(cls._unescape_name(node.attr, ".")))
                node = node.value
                continue
            index = node.slice
            if isinstance(index, ast.Constant) and isinstance(index.value, str) and index.value:
                segments.insert(0, cls._pointer_segment(index.value))
            elif (
                isinstance(index, ast.Constant)
                and isinstance(index.value, int)
                and not isinstance(index.value, bool)
                and index.value >= 0
            ):
                segments.insert(0, str(index.value))
            else:
                raise ValueError(
                    "Subscripts in port calls must be a non-empty string key or a non-negative "
                    "integer index"
                )
            node = node.value
        if not isinstance(node, ast.Name):
            raise ValueError(
                f"Unsupported AST node type for a value path: {type(node).__name__} "
                "(paths start with a port name or 'value')"
            )
        root = cls._unescape_name(node.id, ".")
        return "/".join([root, *segments])

    @staticmethod
    def _pointer_segment(segment: str) -> str:
        """RFC 6901 escaping of a single JSON-pointer segment."""
        return segment.replace("~", "~0").replace("/", "~1")

    @classmethod
    def _parse_ast_call(cls, node: ast.Call) -> UtilCallInput:  # type: ignore[override]
        full_path = cls._extract_path(node.func)
        path_parts = full_path.split(".")

        if path_parts[0] == "actions":
            raise ValueError(
                f"Port calls must be pure: agent calls like '{full_path}(...)' are not allowed"
            )
        if path_parts[0] == "utils":
            path_parts = path_parts[1:]
            if not path_parts:
                raise ValueError(f"Invalid utils namespace: '{full_path}'.")

        operation = cls._unescape_name(".".join(path_parts), ".")
        arguments = resolve_base_arguments(
            operation, cls._parse_call_arguments(node), f"{operation}(...)"
        )

        return UtilCallInput(
            operation=operation,
            arguments=tuple(arguments) if arguments else None,
        )

    @classmethod
    def _argument_path(cls, node: ast.AST) -> str:
        return cls._subscript_path(node)


def parse_util_call(expression: str) -> UtilCallInput:
    """Parse a pure port-call expression into a :class:`UtilCallInput`.

    Used for port validators and effects. ``value`` refers to the port's own value,
    other names refer to sibling ports (``other`` or ``other.child``); operator sugar,
    nested calls, literals, keyword arguments, lists and dicts are supported (see
    :class:`PortCallParser`).

    Examples:
        ``parse_util_call("value > 3")`` and ``parse_util_call("gt(value, 3)")`` both
        give ``gt`` with ``a`` bound to ``value_path="value"`` and ``b`` to
        ``value_literal=3``; ``parse_util_call("gt(value, other.min)")`` references
        ``other/min``.

    Raises:
        ValueError: If the expression is not a call, does not parse, or contains an
            agent call.
    """
    return PortCallParser.parse_expression(expression)


def coerce_util_call(call: "str | UtilCallInput") -> UtilCallInput:
    """Return ``call`` as a :class:`UtilCallInput`, parsing it if it is an expression."""
    if isinstance(call, UtilCallInput):
        return call
    return parse_util_call(call)



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


def normalize_expression(expression: str) -> str:
    """The ``source`` form of an authored expression: stripped, without the blok ``@`` prefix."""
    return expression.strip().removeprefix("@").strip()
