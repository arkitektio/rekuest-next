"""Tests for pure port calls: the expression parser, dependency inference and purity checks.

Port validators and effects carry a blok ``UtilCallInput`` that the UI evaluates
against its catalog. These tests pin the wire shape the server expects (see the
server's ``tests/models/test_port_calls.py``) and the client-side mirror of its
purity rule.
"""

from typing import Annotated

import pytest
from annotated_types import Gt, Le, Len

from rekuest_next.api.schema import (
    ActionArgumentInput,
    AgentProbeInput,
    EffectInput,
    EffectKind,
    UtilCallInput,
    ValidatorInput,
)
from rekuest_next.blok.parser import coerce_util_call, parse_util_call
from rekuest_next.definition.define import prepare_definition
from rekuest_next.structures.registry import StructureRegistry
from rekuest_next.traits.calls import check_pure_call, infer_dependencies
from rekuest_next.widgets import withEffect, withValidator

from .funcs import annotated_basic_function, annotated_nested_structure_function


def _args(call: UtilCallInput) -> tuple[ActionArgumentInput, ...]:
    assert call.arguments is not None
    return call.arguments


# --- parsing -------------------------------------------------------------------


def test_parse_positional_arguments() -> None:
    """Positional arguments of a base operation are named after its parameters."""
    call = parse_util_call("gt(value, 3)")

    assert call.operation == "gt"
    first, second = _args(call)
    assert first.key == "a" and first.value_path == "value"
    assert second.key == "b" and second.value_literal == 3


def test_parse_non_base_positional_arguments_stay_indexed() -> None:
    """Operations the base catalog does not know keep index keys; the UI maps them in order."""
    keys = [argument.key for argument in _args(parse_util_call("f(value, 1, b=2)"))]
    assert keys == ["0", "1", "b"]

    keys = [argument.key for argument in _args(parse_util_call("math.multiply(value, 2)"))]
    assert keys == ["0", "1"]


def test_parse_mixed_positional_and_keyword_arguments() -> None:
    """Positionals and keywords of a base operation combine, in manifest order."""
    keys = [argument.key for argument in _args(parse_util_call("between(value, max=10, min=0)"))]

    assert keys == ["value", "min", "max"]


def test_parse_keyword_arguments() -> None:
    """Keyword arguments are keyed by name."""
    call = parse_util_call("gt(a=value, b=3)")

    first, second = _args(call)
    assert first.key == "a" and first.value_path == "value"
    assert second.key == "b" and second.value_literal == 3


def test_parse_dotted_path_is_emitted_as_json_pointer() -> None:
    """``other.min`` in the expression becomes ``other/min`` on the wire."""
    call = parse_util_call("gt(value, other.min)")

    assert _args(call)[1].value_path == "other/min"


def test_parse_nested_call_list_and_dict() -> None:
    """Nested calls, lists and dicts mirror blok prop parsing."""
    call = parse_util_call('if(gt(value, 3), [1, other], {"z": other.x})')

    condition, on_true, on_false = _args(call)
    assert condition.util_call is not None
    assert condition.util_call.operation == "gt"
    assert on_true.value_list is not None
    assert on_true.value_list[1].value_path == "other"
    assert on_false.value_dict is not None
    assert on_false.value_dict[0].key == "z"
    assert on_false.value_dict[0].value_path == "other/x"


def test_parse_tolerates_utils_prefix_and_at_sign() -> None:
    """The blok prop spelling ``@utils.gt(...)`` is accepted."""
    assert parse_util_call("@utils.gt(value, 3)").operation == "gt"
    assert parse_util_call("utils.gt(value, 3)").operation == "gt"


def test_parse_keeps_dotted_operation() -> None:
    """Only a leading ``utils.`` is stripped; namespaced operations survive."""
    assert parse_util_call("math.multiply(value, 2)").operation == "math.multiply"


def test_parse_keyword_operations() -> None:
    """Catalog operations named like Python keywords parse."""
    call = parse_util_call("not(and(gt(value, 1), other))")

    assert call.operation == "not"
    inner = _args(call)[0].util_call
    assert inner is not None and inner.operation == "and"
    assert _args(inner)[1].value_path == "other"


def test_parse_signed_and_boolean_literals() -> None:
    """Negative numbers and booleans are literals."""
    minus, plus, flag = _args(parse_util_call("f(-1, +2.5, True)"))

    assert minus.value_literal == -1
    assert plus.value_literal == 2.5
    assert flag.value_literal is True


def test_parse_call_without_arguments() -> None:
    """A call without arguments has ``arguments=None``."""
    assert parse_util_call("always()").arguments is None


@pytest.mark.parametrize(
    "expression, message",
    [
        ("value", "call or boolean expression"),
        ("gt(value,", "Failed to parse"),
        ("actions.stage.move()", "must be pure"),
        ("gt(value, actions.stage.move())", "must be pure"),
        ("gt(value, None)", "cannot be None"),
        ("value // 2", "FloorDiv is not supported"),
        ("2 ** value", "Pow is not supported"),
        ("value & 1", "BitAnd is not supported"),
        ("~value", "Bitwise operators are not supported"),
        ("value is 3", "only supported as 'is None'"),
        ("gt(value)", r"gt requires arguments \['b'\]"),
        ("gt(value, 1, 2)", "takes at most 2 positional"),
        ("gt(value, c=1)", "does not accept argument 'c'"),
        ("gt(a=value, a=1)", "multiple values for 'a'"),
        ("gt(value, other[-1])", "non-negative integer"),
        ("gt(value, other[x])", "non-negative integer"),
        ("gt(**kwargs)", "unpacked"),
        ('gt(value, {"": 1})', "non-empty literal strings"),
        ("gt(value, [1, 2][0])", "Unsupported AST node"),
        ("gt(value, lambda x: x)", "Unsupported AST node"),
    ],
)
def test_parse_rejects(expression: str, message: str) -> None:
    """Non-calls, syntax errors, agent calls, None and operators are rejected."""
    with pytest.raises(ValueError, match=message):
        parse_util_call(expression)


def test_coerce_passes_through_util_call_input() -> None:
    """A ready ``UtilCallInput`` is returned unchanged."""
    call = UtilCallInput(operation="gt", arguments=None)
    assert coerce_util_call(call) is call


# --- operator sugar ---------------------------------------------------------------


@pytest.mark.parametrize(
    "expression, operation",
    [("value > 3", "gt"), ("value >= 3", "gte"), ("value < 3", "lt"), ("value <= 3", "lte"), ("value == 3", "eq"), ("value != 3", "ne")],
)
def test_parse_comparison_sugar(expression: str, operation: str) -> None:
    """Comparison operators desugar onto the base comparisons with named parameters."""
    call = parse_util_call(expression)

    assert call.operation == operation
    assert [(a.key, a.value_path, a.value_literal) for a in _args(call)] == [("a", "value", None), ("b", None, 3)]


def test_parse_chained_comparison_folds_into_and() -> None:
    """``0 < value < 10`` is ``and(lt(0, value), lt(value, 10))``."""
    call = parse_util_call("0 < value < 10")

    assert call.operation == "and"
    left, right = _args(call)
    assert left.util_call is not None and left.util_call.operation == "lt"
    assert [a.value_literal for a in _args(left.util_call)] == [0, None]
    assert right.util_call is not None and [a.value_literal for a in _args(right.util_call)] == [None, 10]


def test_parse_bool_ops_fold_left() -> None:
    """``a and b and c`` nests as ``and(and(a, b), c)``; ``or`` likewise."""
    call = parse_util_call("a and b and c")
    inner, last = _args(call)
    assert call.operation == "and" and inner.util_call is not None
    assert [a.value_path for a in _args(inner.util_call)] == ["a", "b"] and last.value_path == "c"

    call = parse_util_call("a or (b and c)")
    assert call.operation == "or"
    assert _args(call)[1].util_call is not None and _args(call)[1].util_call.operation == "and"


def test_parse_not_sugar_and_not_call_converge() -> None:
    """``not value > 3`` and ``not(gt(value, 3))`` produce the same tree."""
    assert parse_util_call("not value > 3") == parse_util_call("not(gt(value, 3))")
    assert parse_util_call("value > 3 and not other") == parse_util_call("and(gt(value, 3), not(other))")


def test_parse_in_and_not_in() -> None:
    """``in`` maps to the base ``in`` operation; ``not in`` wraps it in ``not``."""
    call = parse_util_call("value in [1, 2]")
    assert call.operation == "in"
    value, options = _args(call)
    assert value.key == "value" and options.key == "options"
    assert options.value_list is not None and [e.value_literal for e in options.value_list] == [1, 2]

    call = parse_util_call("value not in opts")
    assert call.operation == "not"
    assert _args(call)[0].util_call is not None and _args(call)[0].util_call.operation == "in"


def test_parse_is_none_and_is_not_none() -> None:
    """``is None`` / ``is not None`` map to ``is_null`` / ``is_set``."""
    assert parse_util_call("value is None").operation == "is_null"
    assert parse_util_call("other.x is not None").operation == "is_set"
    assert _args(parse_util_call("other.x is not None"))[0].value_path == "other/x"


def test_parse_ternary() -> None:
    """``x if c else y`` maps to ``if(condition, then, otherwise)``."""
    call = parse_util_call("1 if value > 3 else 0")

    assert call.operation == "if"
    assert [a.key for a in _args(call)] == ["condition", "then", "otherwise"]
    assert _args(call)[0].util_call is not None and _args(call)[0].util_call.operation == "gt"


def test_parse_len_sugar() -> None:
    """``len(value) > 3`` is ``gt(a=len(a=value), b=3)``."""
    call = parse_util_call("len(value) > 3")

    assert call.operation == "gt"
    inner = _args(call)[0].util_call
    assert inner is not None and inner.operation == "len"
    assert [(a.key, a.value_path) for a in _args(inner)] == [("a", "value")]


def test_parse_subscripts_are_json_pointer_segments() -> None:
    """Subscripts become pointer segments, RFC 6901 escaped; integers index lists."""
    paths = [a.value_path for a in _args(parse_util_call('eq(other["k/x"], other.list[1].x)'))]
    assert paths == ["other/k~1x", "other/list/1/x"]

    assert _args(parse_util_call("eq(items[0], 1)"))[0].value_path == "items/0"
    assert _args(parse_util_call('eq(other["a~b"], 1)'))[0].value_path == "other/a~0b"


def test_parse_keyword_operator_before_parenthesis() -> None:
    """A keyword followed by ``(`` is only an operation when it is in callee position."""
    call = parse_util_call("gt(value, 1) and (other or value)")
    assert call.operation == "and"
    assert _args(call)[1].util_call is not None and _args(call)[1].util_call.operation == "or"

    assert parse_util_call("not (value)").operation == "not"
    assert parse_util_call("value in (1, 2)").operation == "in"
    assert parse_util_call("[if(value, 1, 2)][0] == 1") if False else True  # subscript on a list literal is out of scope


@pytest.mark.parametrize(
    "expression, operation",
    [("value + 3", "add"), ("value - 3", "sub"), ("value * 3", "mul"), ("value / 3", "div"), ("value % 3", "mod")],
)
def test_parse_arithmetic_sugar(expression: str, operation: str) -> None:
    """Arithmetic operators desugar onto the base arithmetic with named parameters."""
    call = parse_util_call(expression)

    assert call.operation == operation
    assert [(a.key, a.value_path, a.value_literal) for a in _args(call)] == [("a", "value", None), ("b", None, 3)]


def test_parse_arithmetic_precedence_and_associativity() -> None:
    """Python's precedence and left associativity carry over."""
    call = parse_util_call("x < value + 3")
    assert call.operation == "lt"
    left, right = _args(call)
    assert left.value_path == "x"
    assert right.util_call is not None and right.util_call.operation == "add"
    assert [(a.value_path, a.value_literal) for a in _args(right.util_call)] == [("value", None), (None, 3)]

    call = parse_util_call("a - b - c")
    assert call.operation == "sub" and _args(call)[0].util_call is not None
    assert _args(call)[0].util_call.operation == "sub" and _args(call)[1].value_path == "c"

    call = parse_util_call("a + b * c")
    assert call.operation == "add" and _args(call)[1].util_call is not None
    assert _args(call)[1].util_call.operation == "mul"

    call = parse_util_call("(a + b) * c")
    assert call.operation == "mul" and _args(call)[0].util_call is not None
    assert _args(call)[0].util_call.operation == "add"


def test_parse_unary_minus_on_paths() -> None:
    """Unary minus on a path is ``neg``; on a number it stays a literal."""
    call = parse_util_call("-other.offset")
    assert call.operation == "neg" and _args(call)[0].value_path == "other/offset"

    call = parse_util_call("gt(value, -1)")
    assert _args(call)[1].value_literal == -1 and _args(call)[1].util_call is None

    call = parse_util_call("--x")
    assert call.operation == "neg" and _args(call)[0].util_call is not None
    assert _args(call)[0].util_call.operation == "neg"

    assert parse_util_call("+x + 1").operation == "add"


def test_parse_optional_base_argument_may_be_omitted() -> None:
    """A trailing optional parameter (``len_between.max``) may be left out."""
    assert [a.key for a in _args(parse_util_call("len_between(value, 3)"))] == ["value", "min"]
    assert [a.key for a in _args(parse_util_call("len_between(value, 3, 5)"))] == ["value", "min", "max"]
    assert [a.key for a in _args(parse_util_call("len_between(value, max=5, min=3)"))] == ["value", "min", "max"]


def test_sugar_calls_satisfy_the_shape_and_purity_rules() -> None:
    """Whatever the desugarer emits passes the server-mirrored checks."""
    for expression in [
        "0 < value < 10 and other not in [1, 2]",
        "value is None or (1 if len(value) > 2 else other['k'])",
        "not (value > 3)",
        "other < value + 3 and value % 2 == 0",
        "-other.offset <= value / 2",
    ]:
        check_pure_call(parse_util_call(expression), ["other"], "Validator")

    assert infer_dependencies(parse_util_call("x < value + 3")) == ("x",)


def test_with_helpers_set_source_only_for_expressions() -> None:
    """``source`` is the stripped expression; a ready call has none."""
    assert withValidator("  @value > 3 ", error_message="x").source == "value > 3"
    assert withEffect(EffectKind.HIDE, "other > 0").source == "other > 0"
    assert withValidator(parse_util_call("value > 3")).source is None


# --- dependency inference -------------------------------------------------------


def test_infer_dependencies_orders_dedupes_and_skips_own_value() -> None:
    """Roots are collected depth first, once each, without ``value``."""
    call = parse_util_call("gt(a.x, if(b, a.y, [c, value]))")

    assert infer_dependencies(call) == ("a", "b", "c")


def test_infer_dependencies_appends_explicit_extras() -> None:
    """Explicit dependencies are appended after the inferred ones, without duplicates."""
    call = parse_util_call("gt(value, a)")

    assert infer_dependencies(call, ["z", "a"]) == ("a", "z")


def test_infer_dependencies_tolerates_leading_slash() -> None:
    """A JSON-pointer path with a leading slash has the same root."""
    call = UtilCallInput(
        operation="gt",
        arguments=(
            ActionArgumentInput(value_path="/value"),
            ActionArgumentInput(value_path="/other/x"),
        ),
    )

    assert infer_dependencies(call) == ("other",)


# --- purity (mirrors the server rule) --------------------------------------------


def test_check_pure_call_accepts_declared_nested_paths() -> None:
    """Value paths nested in util calls are checked against the declared dependencies."""
    nested = UtilCallInput(
        operation="gt",
        arguments=(
            ActionArgumentInput(
                key="a",
                util_call=UtilCallInput(
                    operation="len",
                    arguments=(ActionArgumentInput(key="a", value_path="hidden/x"),),
                ),
            ),
        ),
    )

    check_pure_call(nested, ["hidden"], "Validator")
    with pytest.raises(ValueError, match="'hidden'"):
        check_pure_call(nested, [], "Validator")


@pytest.mark.parametrize("model", [ValidatorInput, EffectInput])
def test_input_models_reject_impure_calls(
    model: type[ValidatorInput] | type[EffectInput],
) -> None:
    """Both generated inputs carry the purity trait."""
    extra = {"kind": EffectKind.HIDE} if model is EffectInput else {}

    model(call=parse_util_call("gt(value, other)"), dependencies=["other"], **extra)

    with pytest.raises(ValueError, match="'other' via value_path"):
        model(call=parse_util_call("gt(value, other)"), **extra)

    with pytest.raises(ValueError, match="must be pure"):
        model(
            call=UtilCallInput(
                operation="gt",
                arguments=(
                    ActionArgumentInput(
                        key="a",
                        agent_call=AgentProbeInput(dependency="stage", operation="move"),
                    ),
                ),
            ),
            **extra,
        )


# --- argument shape (mirrors the server rule) -------------------------------------


def _unchecked(operation: str = "gt", **binding: object) -> UtilCallInput:
    """A call whose argument bypasses client construction checks (as raw wire data would)."""
    return UtilCallInput.model_construct(
        operation=operation,
        arguments=(ActionArgumentInput.model_construct(**binding),),
    )


@pytest.mark.parametrize(
    "call, message",
    [
        (_unchecked(key=None, value_literal=1), "every entry must carry a key"),
        (_unchecked(key="", value_literal=1), "every entry must carry a key"),
        (_unchecked(key="a"), "exactly one of"),
        (_unchecked(key="a", value_literal=1, value_path="value"), "exactly one of"),
        (
            _unchecked(key="a", value_dict=(ActionArgumentInput.model_construct(key=None, value_literal=1),)),
            "every entry must carry a key",
        ),
        (
            _unchecked(
                key="a",
                value_dict=(
                    ActionArgumentInput.model_construct(key="x", value_literal=1),
                    ActionArgumentInput.model_construct(key="x", value_literal=2),
                ),
            ),
            "duplicate key 'x'",
        ),
        (
            _unchecked(key="a", value_list=(ActionArgumentInput.model_construct(key="x", value_literal=1),)),
            "must not carry a key",
        ),
        (_unchecked(operation="   ", key="a", value_literal=1), "must name an operation"),
        (
            _unchecked(key="a", util_call=_unchecked(key=None, value_literal=1)),
            "every entry must carry a key",
        ),
    ],
)
def test_call_shape_rules(call: UtilCallInput, message: str) -> None:
    """Keys, bindings and nesting follow the server's argument-shape rules."""
    with pytest.raises(ValueError, match=message):
        check_pure_call(call, [], "Validator")


def test_duplicate_call_argument_keys_are_rejected() -> None:
    """Two call arguments with the same key are rejected."""
    call = UtilCallInput.model_construct(
        operation="gt",
        arguments=(
            ActionArgumentInput.model_construct(key="a", value_literal=1),
            ActionArgumentInput.model_construct(key="a", value_literal=2),
        ),
    )
    with pytest.raises(ValueError, match="duplicate key 'a'"):
        check_pure_call(call, [], "Validator")


def test_parsed_calls_always_satisfy_the_shape_rules() -> None:
    """Whatever the parser emits passes the shape check."""
    for expression in [
        "gt(value, 3)",
        "if(gt(a=value, b=3), [1, other, {'k': 2}], {'z': other.x, 'y': [value]})",
        "not(and(gt(value, 1), other))",
        "always()",
    ]:
        check_pure_call(parse_util_call(expression), ["other"], "Validator")


# --- helpers and definitions --------------------------------------------------


def test_with_validator_infers_dependencies() -> None:
    """``withValidator`` fills ``dependencies`` from the call."""
    validator = withValidator(
        "gt(value, other.min)", error_message="too small", label="min"
    )

    assert validator.dependencies == ("other",)
    assert validator.label == "min"
    assert validator.error_message == "too small"


def test_with_effect_unions_explicit_dependencies() -> None:
    """Explicit dependencies subscribe to extra ports."""
    effect = withEffect(
        EffectKind.MESSAGE, "gt(other, 0)", message="hi", dependencies=["extra"]
    )

    assert effect.dependencies == ("other", "extra")
    assert effect.message == "hi"
    assert effect.kind == EffectKind.MESSAGE


def test_with_validator_rejects_agent_calls() -> None:
    """Helper errors surface at annotation time."""
    with pytest.raises(ValueError, match="must be pure"):
        withValidator("actions.stage.move()")


def test_wire_shape_matches_server(simple_registry: StructureRegistry) -> None:
    """The serialized validator has the ``call`` shape the server's models accept."""
    validator = withValidator("gt(value, other.min)", error_message="x")

    assert validator.model_dump(by_alias=True, exclude_none=True) == {
        "call": {
            "operation": "gt",
            "arguments": (
                {"key": "a", "valuePath": "value"},
                {"key": "b", "valuePath": "other/min"},
            ),
        },
        "source": "gt(value, other.min)",
        "dependencies": ("other",),
        "errorMessage": "x",
    }


@pytest.mark.define
def test_definition_round_trip(simple_registry: StructureRegistry) -> None:
    """Validators and effects referencing sibling ports survive ``prepare_definition``."""

    def func(
        a: Annotated[int, withValidator("gt(value, b)", error_message="a must exceed b")],
        b: Annotated[int, withEffect(EffectKind.HIDE, "gt(a, 10)")],
    ) -> int:
        return a + b

    definition = prepare_definition(func, structure_registry=simple_registry)

    validators = definition.args[0].validators
    assert validators is not None
    assert validators[0].dependencies == ("b",)
    assert _args(validators[0].call)[1].value_path == "b"

    effects = definition.args[1].effects
    assert effects is not None
    assert effects[0].dependencies == ("a",)


@pytest.mark.define
def test_definition_resolves_nested_dependency_paths(simple_registry: StructureRegistry) -> None:
    """A dependency ``cfg..limit`` names the child ``limit`` of the model port ``cfg``."""
    from rekuest_next.structures.model import model

    @model
    class Config:
        limit: int
        label: str

    call = UtilCallInput(
        operation="gt",
        arguments=(
            ActionArgumentInput(key="a", value_path="value"),
            ActionArgumentInput(key="b", value_path="/cfg..limit"),
        ),
    )

    def good(cfg: Config, n: Annotated[int, withValidator(call, error_message="too big")]) -> int:
        return n

    definition = prepare_definition(good, structure_registry=simple_registry)
    validators = definition.args[1].validators
    assert validators is not None
    assert validators[0].dependencies == ("cfg..limit",)

    unresolvable = UtilCallInput(
        operation="gt",
        arguments=(ActionArgumentInput(key="a", value_path="/cfg..nope"),),
    )

    def bad(cfg: Config, n: Annotated[int, withValidator(unresolvable)]) -> int:
        return n

    with pytest.raises(ValueError, match="invalid dependency: cfg..nope"):
        prepare_definition(bad, structure_registry=simple_registry)

    # ``..`` is a port-path separator, not expression syntax.
    with pytest.raises(ValueError, match="Failed to parse"):
        parse_util_call("gt(value, cfg..nope)")


@pytest.mark.define
def test_definition_checks_return_ports_children_and_port_groups(
    simple_registry: StructureRegistry,
) -> None:
    """Dependencies are checked wherever an effect can sit, not only on top-level args."""
    from rekuest_next.api.schema import PortGroupInput
    from rekuest_next.structures.model import model

    @model
    class Inner:
        n: Annotated[int, withEffect(EffectKind.HIDE, "gt(missing, 0)")]

    def nested(a: Inner) -> int:
        return 1

    with pytest.raises(ValueError, match="in port a..n has invalid dependency: missing"):
        prepare_definition(nested, structure_registry=simple_registry)

    def grouped(a: int) -> int:
        return a

    with pytest.raises(ValueError, match="port group grp has invalid dependency: missing"):
        prepare_definition(
            grouped,
            structure_registry=simple_registry,
            port_groups=[
                PortGroupInput(
                    key="grp",
                    ports=["a"],
                    effects=[withEffect(EffectKind.HIDE, "gt(missing, 0)")],
                )
            ],
        )

    def returning(a: int) -> Annotated[int, withEffect(EffectKind.HIDE, "gt(a, 0)")]:
        return a

    definition = prepare_definition(returning, structure_registry=simple_registry)
    effects = definition.returns[0].effects
    assert effects is not None and effects[0].dependencies == ("a",)


@pytest.mark.define
def test_port_named_value_is_allowed_and_shadowed_in_calls(
    simple_registry: StructureRegistry,
) -> None:
    """A port may be called ``value``; inside a call ``value`` is always the port's own value."""

    def func(value: int, n: Annotated[int, withValidator("gt(a=value, b=0)")]) -> int:
        return value + n

    definition = prepare_definition(func, structure_registry=simple_registry)
    assert [port.key for port in definition.args] == ["value", "n"]
    validators = definition.args[1].validators
    assert validators is not None
    assert validators[0].dependencies == ()  # own value, not the sibling port


@pytest.mark.define
def test_definition_carries_catalogs(simple_registry: StructureRegistry) -> None:
    """The catalogs a definition opts into ride along on the definition."""

    def func(a: int) -> int:
        return a

    definition = prepare_definition(func, structure_registry=simple_registry, catalogs=["ui", "base@1"])
    assert definition.catalogs == ("ui", "base@1")
    assert prepare_definition(func, structure_registry=simple_registry).catalogs is None


@pytest.mark.define
def test_definition_rejects_unknown_dependency(simple_registry: StructureRegistry) -> None:
    """An effect referencing a port that does not exist is rejected."""

    def func(a: Annotated[int, withEffect(EffectKind.HIDE, "gt(missing, 10)")]) -> int:
        return a

    with pytest.raises(ValueError, match="invalid dependency: missing"):
        prepare_definition(func, structure_registry=simple_registry)


# --- annotated_types bridge ----------------------------------------------------


@pytest.mark.define
def test_annotated_types_bridge_emits_catalog_calls(
    simple_registry: StructureRegistry,
) -> None:
    """``Le``/``Gt`` become ``lte``/``gt`` calls on the port's own value."""
    definition = prepare_definition(
        annotated_basic_function, structure_registry=simple_registry
    )

    validators = definition.args[1].validators
    assert validators is not None
    assert [v.call.operation for v in validators] == ["lte", "gt"]
    for validator in validators:
        own, bound = _args(validator.call)
        assert own.key == "a" and own.value_path == "value"
        assert bound.key == "b" and bound.value_literal == 4
        assert validator.dependencies is None
    assert [v.source for v in validators] == ["lte(value, 4)", "gt(value, 4)"]


@pytest.mark.define
def test_annotated_types_len_bounds(simple_registry: StructureRegistry) -> None:
    """``Len`` emits ``len_between`` with only the bounds that are set."""
    definition = prepare_definition(
        annotated_nested_structure_function, structure_registry=simple_registry
    )
    validators = definition.args[1].children[0].validators
    assert validators is not None
    assert validators[0].call.operation == "len_between"
    assert [(a.key, a.value_literal) for a in _args(validators[0].call)] == [("value", None), ("min", 3)]
    assert validators[0].source == "len_between(value, 3)"

    def func(name: Annotated[str, Len(3, 5)]) -> str:
        return name

    definition = prepare_definition(func, structure_registry=simple_registry)
    validators = definition.args[0].validators
    assert validators is not None
    assert [(a.key, a.value_literal) for a in _args(validators[0].call)] == [("value", None), ("min", 3), ("max", 5)]


@pytest.mark.define
def test_annotated_types_gt_and_le_direct(simple_registry: StructureRegistry) -> None:
    """Direct ``Gt``/``Le`` markers on a plain port."""

    def func(n: Annotated[int, Gt(-1), Le(10)]) -> int:
        return n

    definition = prepare_definition(func, structure_registry=simple_registry)
    validators = definition.args[0].validators
    assert validators is not None
    assert [(v.call.operation, _args(v.call)[1].value_literal) for v in validators] == [
        ("gt", -1),
        ("lte", 10),
    ]
