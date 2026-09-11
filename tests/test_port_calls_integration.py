"""Integration tests for port calls (validators and effects) against a real server.

The server stores a validator/effect as a pure blok ``UtilCall`` and enforces the same
rules the client mirrors (keyed arguments, purity, declared dependencies), plus one the
client cannot: when a definition names a UI catalog, every operation must be registered
there with matching parameter names. These tests register real functions against the
shared docker deployment and read the stored calls back.
"""

import asyncio
from typing import Annotated

import pytest
from dokker import Deployment

from rekuest_next.api.schema import (
    ActionArgumentInput,
    CatalogArgumentInput,
    CatalogOperationInput,
    CatalogValueKind,
    EffectKind,
    ImplementationInput,
    UtilCallInput,
    ValidatorInput,
    abase_catalog,
    aimplement_agent,
    amy_implementation_at,
    aregister_ui_catalog,
)
from rekuest_next.blok.parser import parse_util_call
from rekuest_next.definition.define import prepare_definition
from rekuest_next.remote import acall
from rekuest_next.widgets import withEffect, withValidator

from .conftest import CONNECT_TIMEOUT, build_fresh_rekuest

NESTED = 'if(value > start, [1, stop, {"unicode": "d\u00e9j\u00e0 vu", "neg": -1.5}], not(gt(value, 0)))'


def crop(
    start: Annotated[int, withValidator("gt(a=value, b=-1)", error_message="Must not be negative")],
    stop: Annotated[int, withValidator(NESTED, error_message="Stop must exceed start", label="ordered")],
    note: Annotated[str, withEffect(EffectKind.HIDE, "stop > 1000 and start > 0")] = "",
) -> int:
    """Crop a range.

    Args:
        start: first index
        stop: last index
        note: a note
    """
    return stop - start


def offset(value: int, n: Annotated[int, withValidator("gt(a=value, b=0)", error_message="positive")]) -> int:
    """Offset.

    Args:
        value: base
        n: amount
    """
    return value + n


EFFECTS_QUERY = """
query Effects($interface: String) {
  myImplementationAt(interface: $interface) {
    action {
      args {
        key
        effects {
          kind
          dependencies
          source
          callJson
          call {
            operation
            arguments { key valuePath utilCall { operation arguments { key valuePath valueLiteral } } }
          }
        }
      }
    }
  }
}
"""


async def _run(app, body):  # noqa: ANN001, ANN202
    async with app as app:
        await app.aconnect(timeout=CONNECT_TIMEOUT)
        task = asyncio.create_task(app.aloop())
        try:
            return await body(app)
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_port_calls_round_trip(deployment: Deployment) -> None:
    """Validators and effects come back from the server exactly as declared."""
    app = build_fresh_rekuest(deployment, token="standalone_token")
    app.register(crop)
    app.register(offset)

    async def body(app):  # noqa: ANN001, ANN202
        impl = await amy_implementation_at("crop", rath=app.rath)
        start, stop, note = impl.action.args

        (validator,) = start.validators
        assert validator.error_message == "Must not be negative"
        assert validator.source == "gt(a=value, b=-1)"
        assert validator.call_json["operation"] == "gt"
        assert validator.call.operation == "gt"
        assert [(a.key, a.value_path, a.value_literal) for a in validator.call.arguments] == [
            ("a", "value", None),
            ("b", None, -1),
        ]
        assert validator.dependencies == ()

        (validator,) = stop.validators
        assert validator.label == "ordered"
        assert validator.dependencies == ("start", "stop")
        assert validator.call.operation == "if"
        cond, on_true, on_false = validator.call.arguments
        assert cond.util_call.operation == "gt"
        assert [(a.key, a.value_path) for a in cond.util_call.arguments] == [("a", "value"), ("b", "start")]
        assert validator.call_json["arguments"][0]["util_call"]["arguments"][1]["value_path"] == "start"
        assert on_true.value_list[1].value_path == "stop"
        literals = {a.key: a.value_literal for a in on_true.value_list[2].value_dict}
        assert literals == {"unicode": "d\u00e9j\u00e0 vu", "neg": -1.5}
        assert on_false.util_call.operation == "not"
        # depth 3: the innermost gt(value, 0) is still fully selected
        inner = on_false.util_call.arguments[0].util_call
        assert inner.operation == "gt"
        assert [a.value_literal for a in inner.arguments] == [None, 0]
        assert impl.diagnostics == ()

        result = await app.rath.aquery(EFFECTS_QUERY, {"interface": "crop"})
        note_port = next(a for a in result.data["myImplementationAt"]["action"]["args"] if a["key"] == "note")
        (effect,) = note_port["effects"]
        assert effect["kind"] == "HIDE"
        assert effect["dependencies"] == ["stop", "start"]
        assert effect["source"] == "stop > 1000 and start > 0"
        assert effect["call"]["operation"] == "and"
        assert [a["utilCall"]["operation"] for a in effect["call"]["arguments"]] == ["gt", "gt"]
        assert effect["callJson"]["arguments"][1]["util_call"]["arguments"][0]["value_path"] == "start"

        # a port may be named ``value``; in ``offset``'s validator ``value`` is n's own value
        impl = await amy_implementation_at("offset", rath=app.rath)
        value_port, n_port = impl.action.args
        assert value_port.key == "value"
        assert n_port.validators[0].dependencies == ()
        assert await acall(impl, postman=app.postman, structure_registry=app.structure_registry, value=2, n=3) == 5

        # the function itself is unaffected
        impl = await amy_implementation_at("crop", rath=app.rath)
        assert await acall(impl, postman=app.postman, structure_registry=app.structure_registry, start=2, stop=5) == 3

    await _run(app, body)


def _bypass_definition(structure_registry, validator: ValidatorInput):  # noqa: ANN001, ANN202
    """A definition whose validator skipped every client check, as a hand-rolled client could send."""

    def func(a: int, b: int) -> int:
        """Add.

        Args:
            a: left
            b: right
        """
        return a + b

    definition = prepare_definition(func, structure_registry=structure_registry)
    arg = definition.args[0].model_copy(update={"validators": (validator,)})
    return definition.model_copy(update={"args": (arg, definition.args[1])})


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize(
    "validator, message",
    [
        (
            ValidatorInput.model_construct(call=parse_util_call("gt(value, ghost)"), dependencies=()),
            "via value_path",
        ),
        (
            ValidatorInput.model_construct(
                call=UtilCallInput.model_construct(
                    operation="gt",
                    arguments=(ActionArgumentInput.model_construct(key=None, value_literal=1),),
                ),
                dependencies=(),
            ),
            "every entry must carry a key",
        ),
        (
            ValidatorInput.model_construct(
                call=UtilCallInput.model_construct(
                    operation="gt",
                    arguments=(ActionArgumentInput.model_construct(key="a", value_path="value"),),
                ),
                dependencies=(),
            ),
            "requires arguments \\['b'\\]",
        ),
        (
            ValidatorInput.model_construct(
                call=UtilCallInput.model_construct(
                    operation="between",
                    arguments=(
                        ActionArgumentInput.model_construct(key="a", value_path="value"),
                        ActionArgumentInput.model_construct(key="b", value_literal=1),
                    ),
                ),
                dependencies=(),
            ),
            "does not accept arguments \\['a', 'b'\\]",
        ),
        (
            ValidatorInput.model_construct(call=parse_util_call("gt(value, b)"), dependencies=("b",)),
            None,
        ),
    ],
)
async def test_server_enforces_call_rules_independently(
    deployment: Deployment, simple_registry, validator: ValidatorInput, message: str | None  # noqa: ANN001
) -> None:
    """The server rejects what the client would have rejected, even when the client is bypassed."""
    app = build_fresh_rekuest(deployment, token="btest_token")

    async def body(app):  # noqa: ANN001, ANN202
        definition = _bypass_definition(app.structure_registry, validator)
        coro = aimplement_agent(
            name=app.agent.name,
            implementations=[ImplementationInput(definition=definition, interface="bypass")],
            hash="bypass",
            rath=app.rath,
        )
        if message is None:
            await coro
        else:
            with pytest.raises(Exception, match=message):
                await coro

    await _run(app, body)


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_catalog_validation_at_registration(deployment: Deployment) -> None:
    """Base always applies; a named catalog extends it; unknown operations are stored as warnings."""
    app = build_fresh_rekuest(deployment, token="atest_token")

    async def body(app):  # noqa: ANN001, ANN202
        base = await abase_catalog(rath=app.rath)
        assert base.name == "base" and base.version == 1
        assert [a.key for a in next(op for op in base.operations if op.name == "gt").arguments] == ["a", "b"]

        with pytest.raises(Exception, match="cannot redefine base operations"):
            await aregister_ui_catalog(
                name="port-call-tests",
                components=[],
                widget_defaults=[],
                operations=[CatalogOperationInput(name="gt", returns=CatalogValueKind.BOOL, arguments=[])],
                rath=app.rath,
            )

        catalog = await aregister_ui_catalog(
            name="port-call-tests",
            components=[],
                widget_defaults=[],
            operations=[
                CatalogOperationInput(
                    name="clamp",
                    returns=CatalogValueKind.FLOAT,
                    arguments=[
                        CatalogArgumentInput(key="value", kind=CatalogValueKind.FLOAT),
                        CatalogArgumentInput(key="min", kind=CatalogValueKind.FLOAT),
                        CatalogArgumentInput(key="max", kind=CatalogValueKind.FLOAT),
                    ],
                )
            ],
            rath=app.rath,
        )
        assert catalog.is_registered
        assert [op.name for op in catalog.operations] == ["clamp"]

    await _run(app, body)

    def positional(n: Annotated[int, withValidator("gt(value, 0)", error_message="positive")]) -> int:
        """Positional.

        Args:
            n: number
        """
        return n

    def sugar(n: Annotated[int, withValidator("0 < value <= 10")]) -> int:
        """Sugar.

        Args:
            n: number
        """
        return n

    def extension(n: Annotated[int, withValidator("clamp(value=value, min=0, max=10) == value")]) -> int:
        """Extension.

        Args:
            n: number
        """
        return n

    def arithmetic(x: int, n: Annotated[int, withValidator("x < value + 3")]) -> int:
        """Arithmetic.

        Args:
            x: bound
            n: number
        """
        return n

    def unknown(n: Annotated[int, withValidator("fizz(value)")]) -> int:
        """Unknown.

        Args:
            n: number
        """
        return n

    async def registered_ok(app, interface):  # noqa: ANN001, ANN202
        impl = await amy_implementation_at(interface, rath=app.rath)
        assert impl.diagnostics == ()
        if interface == "arithmetic":
            (validator,) = impl.action.args[1].validators
            assert validator.source == "x < value + 3" and validator.dependencies == ("x",)
            assert validator.call_json["arguments"][1]["util_call"]["operation"] == "add"
        return impl

    def combined(n: Annotated[int, withValidator("fmt(a=clamp(value=value, min=0, max=10), b='x') == 'x'")]) -> int:
        """Combined.

        Args:
            n: number
        """
        return n

    await _run(
        build_fresh_rekuest(deployment, token="atest_token"),
        lambda app: aregister_ui_catalog(
            name="port-call-tests-2",
            components=[],
                widget_defaults=[],
            operations=[
                CatalogOperationInput(
                    name="fmt",
                    returns=CatalogValueKind.STRING,
                    arguments=[CatalogArgumentInput(key="a", kind=CatalogValueKind.ANY), CatalogArgumentInput(key="b", kind=CatalogValueKind.ANY)],
                )
            ],
            rath=app.rath,
        ),
    )

    for func, catalog_names in [
        (positional, None),
        (sugar, ["base@1"]),
        (arithmetic, None),
        (positional, ["port-call-tests"]),
        (extension, ["port-call-tests"]),
        (combined, ["port-call-tests", "port-call-tests-2"]),
    ]:
        ok = build_fresh_rekuest(deployment, token="atest_token")
        ok.register(func, catalogs=catalog_names)
        await _run(ok, lambda app, name=func.__name__: registered_ok(app, name))

    # an operation neither base nor the extension provides registers with a stored warning
    for catalog_names, codes in [
        (None, ["unknown_operation"]),
        (["port-call-tests"], ["unknown_operation"]),
        (["ghost"], ["unknown_operation", "unknown_catalog"]),
        (["base@2", "port-call-tests"], ["unknown_operation", "unknown_catalog"]),
    ]:
        warned = build_fresh_rekuest(deployment, token="atest_token")
        warned.register(unknown, catalogs=catalog_names)

        async def check(app, expected=codes):  # noqa: ANN001, ANN202
            impl = await amy_implementation_at("unknown", rath=app.rath)
            assert [d.code for d in impl.diagnostics] == expected
            assert "'fizz'" in impl.diagnostics[0].message

        await _run(warned, check)

    # argument mismatches on base operations are caught client-side at annotation time
    with pytest.raises(ValueError, match="requires arguments"):
        withValidator("gt(a=value)")
    with pytest.raises(ValueError, match="does not accept argument"):
        withValidator("gt(value, c=1)")
