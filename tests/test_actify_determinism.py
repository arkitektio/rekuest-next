"""Derived ``locks``/``manipulates`` must not depend on the process hash seed.

They feed the definition (and its hash) and generated artefacts such as
``blok.json``; ``list(set(...))`` made their order vary between processes.
"""

from dataclasses import dataclass

from rekuest_next.actors.actify import derive_implementation_details
from rekuest_next.actors.types import RegisterConfig
from rekuest_next.state.decorator import state


@state(required_locks=["zeta", "alpha", "mu"])
@dataclass
class First:
    value: int = 0


@state(required_locks=["beta", "alpha"])
@dataclass
class Second:
    value: int = 0


def touch_both(first: First, second: Second) -> None:
    """Write both states."""
    first.value += 1
    second.value += 1


def test_derived_locks_and_manipulates_are_sorted_and_deduplicated() -> None:
    details = derive_implementation_details(touch_both, RegisterConfig(auto_locks=True))
    assert details.locks == ["alpha", "beta", "mu", "zeta"]
    assert details.manipulates == ["First", "Second"]


def test_explicit_locks_keep_the_users_order() -> None:
    details = derive_implementation_details(
        touch_both, RegisterConfig(locks=["zeta", "alpha"], manipulates=["Second", "First"])
    )
    assert details.locks == ["zeta", "alpha"]
    assert details.manipulates == ["Second", "First"]
