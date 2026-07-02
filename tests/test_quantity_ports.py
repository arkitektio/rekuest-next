"""QUANTITY ports: kanne dimension types become dimensionful ports end to end.

A ``kanne`` dimension type used as a parameter/return annotation is reflected into a
``PortKind.QUANTITY`` port carrying the canonical ``reference_unit``, a ``proposed_units``
list for the UI dropdown, and the ``dimension`` string. On the wire it is an abbreviated
pint string (``"5 mV"``); the actor receives a live kanne quantity back. The proposed-units
list is UI-only — any unit of the same dimension is still valid input. Requires the optional
``units`` extra (kanne).
"""

import pytest

pytest.importorskip("kanne")

from typing import Annotated  # noqa: E402

from kanne import ElectricPotential, Duration, Capacitance  # noqa: E402

from rekuest_next.api.schema import ArgPortInput, PortKind  # noqa: E402
from rekuest_next.definition.define import (  # noqa: E402
    prepare_definition,
    convert_object_to_argport,
    convert_object_to_returnport,
)
from rekuest_next import Units  # noqa: E402
from rekuest_next.structures.registry import StructureRegistry  # noqa: E402
from rekuest_next.structures.serialization.actor import (  # noqa: E402
    expand_inputs,
    shrink_outputs,
)
from rekuest_next.structures.quantities import (  # noqa: E402
    is_pint_quantity,
    dimension_of,
    proposed_units_of,
    resolve_quantity_type,
    matches_dimension,
    expand_quantity,
)

VOLT_DIMENSION = "[mass] * [length] ** 2 / [time] ** 3 / [current]"


class _Shelver:
    """Minimal Shelver — quantity ports never touch the shelve, but the API needs one."""

    async def aput_on_shelve(self, identifier, value):  # noqa: ANN001, ANN201
        return "unused"

    async def aget_from_shelve(self, key):  # noqa: ANN001, ANN201
        return None


@pytest.fixture()
def registry() -> StructureRegistry:
    return StructureRegistry()


def test_kanne_arg_becomes_quantity_port(registry: StructureRegistry) -> None:
    port = convert_object_to_argport(ElectricPotential, "v_init", registry)
    assert port.kind == PortKind.QUANTITY
    assert port.reference_unit == "volt"
    assert port.dimension == VOLT_DIMENSION
    # Bare kanne type → the type's declared proposed units.
    assert tuple(port.proposed_units) == ElectricPotential.proposed_units


def test_kanne_return_becomes_quantity_port(registry: StructureRegistry) -> None:
    port = convert_object_to_returnport(Duration, "exposure", registry)
    assert port.kind == PortKind.QUANTITY
    assert port.reference_unit == "second"
    assert port.dimension == "[time]"
    assert tuple(port.proposed_units) == Duration.proposed_units


def test_with_units_annotation_overrides_proposed_units(registry: StructureRegistry) -> None:
    port = convert_object_to_argport(
        Annotated[Capacitance, Units("pF", "nF")], "cm", registry
    )
    assert port.kind == PortKind.QUANTITY
    assert port.reference_unit == "farad"  # canonical stays the kanne reference unit
    assert tuple(port.proposed_units) == ("pF", "nF")


def test_prepare_definition_stamps_all_unit_fields(registry: StructureRegistry) -> None:
    def measure(v: Annotated[ElectricPotential, Units("mV", "V")]) -> Duration:
        """Measure something.

        Args:
            v (ElectricPotential): the applied voltage
        Returns:
            Duration: the resulting exposure
        """
        return Duration("5 ms")

    definition = prepare_definition(measure, structure_registry=registry)
    arg = definition.args[0]
    assert arg.kind == PortKind.QUANTITY
    assert arg.reference_unit == "volt"
    assert arg.dimension == VOLT_DIMENSION
    assert tuple(arg.proposed_units) == ("mV", "V")
    ret = definition.returns[0]
    assert ret.reference_unit == "second"
    assert tuple(ret.proposed_units) == Duration.proposed_units


@pytest.mark.asyncio
async def test_expand_and_shrink_round_trip(registry: StructureRegistry) -> None:
    def measure(v: ElectricPotential) -> Duration:
        """Measure something.

        Args:
            v (ElectricPotential): the applied voltage
        Returns:
            Duration: the resulting exposure
        """
        return Duration("5 ms")

    definition = prepare_definition(measure, structure_registry=registry)
    shelver = _Shelver()

    inputs = await expand_inputs(definition, {"v": "5 mV"}, registry, shelver)
    assert isinstance(inputs["v"], ElectricPotential)
    assert inputs["v"] == ElectricPotential("5 mV")

    outputs = await shrink_outputs(definition, Duration("5 ms"), registry, shelver)
    assert outputs["return0"] == "5 ms"


@pytest.mark.asyncio
async def test_proposals_are_not_a_hard_allow_list(registry: StructureRegistry) -> None:
    """A unit not in proposed_units but of the same dimension still expands."""
    port = convert_object_to_argport(
        Annotated[Capacitance, Units("nF")], "cm", registry
    )
    # "3.3 pF" is not in the proposed list ["nF"] but is a valid capacitance.
    quantity = await expand_inputs(
        prepare_definition(_cap_fn(), structure_registry=registry),
        {"cm": "3.3 pF"},
        registry,
        _Shelver(),
    )
    assert isinstance(quantity["cm"], Capacitance)
    assert quantity["cm"] == Capacitance("3.3 pF")
    assert "nF" in port.proposed_units  # sanity: the proposal really was just nF


def _cap_fn():  # noqa: ANN202
    def use(cm: Capacitance) -> Capacitance:
        """Use.

        Args:
            cm (Capacitance): capacitance
        Returns:
            Capacitance: capacitance
        """
        return cm

    return use


@pytest.mark.asyncio
async def test_expand_rejects_wrong_dimension(registry: StructureRegistry) -> None:
    definition = prepare_definition(_volt_fn(), structure_registry=registry)
    with pytest.raises(Exception):
        await expand_inputs(definition, {"v": "5 ms"}, registry, _Shelver())


def _volt_fn():  # noqa: ANN202
    def measure(v: ElectricPotential) -> ElectricPotential:
        """Measure.

        Args:
            v (ElectricPotential): voltage
        Returns:
            ElectricPotential: voltage
        """
        return v

    return measure


def test_dimension_is_the_wiring_key() -> None:
    """Wiring compatibility is dimension-based, not unit-based."""
    assert matches_dimension(ElectricPotential("5 mV"), VOLT_DIMENSION)
    assert matches_dimension("500 uV", VOLT_DIMENSION)
    assert not matches_dimension(Duration("5 ms"), VOLT_DIMENSION)


def test_quantity_port_requires_reference_unit() -> None:
    """A QUANTITY port is only well-formed with a reference unit."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ArgPortInput(kind=PortKind.QUANTITY, key="bad", nullable=False)

    ArgPortInput(
        kind=PortKind.QUANTITY,
        key="ok",
        nullable=False,
        reference_unit="volt",
        proposed_units=["mV", "V"],
        dimension="[time]",
    )


def test_bridge_helpers() -> None:
    assert is_pint_quantity(ElectricPotential) is True
    assert is_pint_quantity(int) is False
    assert dimension_of(Duration) == "[time]"
    assert resolve_quantity_type("volt") is ElectricPotential
    assert resolve_quantity_type("bogus-unit") is None
    assert proposed_units_of(Capacitance) == Capacitance.proposed_units


def test_expand_quantity_unknown_unit_errors() -> None:
    with pytest.raises(ValueError, match="no kanne dimension type"):
        expand_quantity("5", "not-a-real-unit")
