"""The base catalog: pure operations every UI implements for port calls.

``base_v1.json`` is a byte-for-byte copy of the server's ``rekuest_core/catalogs/base_v1.json``
(a test diffs them when the server tree is present). The base catalog is implicit for every
definition: its operations are always available, positional call arguments are resolved to its
parameter names, and a UI catalog named by a definition only *extends* it.

This module deliberately imports nothing from ``rekuest_next.api.schema`` so that
``rekuest_next.traits`` (imported by the generated module at import time) can use it.
"""

import functools
import json
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources

BASE_CATALOG_NAME = "base"
BASE_CATALOG_VERSION = 1
VALUE_KINDS = ("STRING", "INT", "FLOAT", "BOOL", "DICT", "LIST", "ANY", "CALLBACK")
"""The ``CatalogValueKind`` names, hard-coded so this module never imports the generated schema."""


@dataclass(frozen=True)
class BaseArgument:
    """A parameter of a base operation."""

    key: str
    kind: str
    required: bool
    description: str | None = None


@dataclass(frozen=True)
class BaseOperation:
    """A base operation; ``arguments`` order is positional order."""

    name: str
    returns: str
    arguments: tuple[BaseArgument, ...]
    description: str | None = None

    @property
    def keys(self) -> tuple[str, ...]:
        """Parameter names in positional order."""
        return tuple(argument.key for argument in self.arguments)

    @property
    def required_keys(self) -> tuple[str, ...]:
        """Parameter names every call must pass, in positional order."""
        return tuple(argument.key for argument in self.arguments if argument.required)


@dataclass(frozen=True)
class BaseCatalog:
    """The parsed manifest."""

    name: str
    version: int
    operations: tuple[BaseOperation, ...]
    description: str | None = None


def _parse(raw: dict) -> BaseCatalog:  # type: ignore[type-arg]
    operations: list[BaseOperation] = []
    seen: set[str] = set()
    for entry in raw["operations"]:
        name = entry["name"]
        if not name or name in seen:
            raise ValueError(f"base catalog: duplicate or empty operation name {name!r}")
        seen.add(name)
        if entry["returns"] not in VALUE_KINDS:
            raise ValueError(f"base catalog: {name} returns unknown kind {entry['returns']!r}")
        arguments: list[BaseArgument] = []
        keys: set[str] = set()
        for argument in entry.get("arguments", []):
            if not argument["key"] or argument["key"] in keys:
                raise ValueError(f"base catalog: {name} has a duplicate or empty argument key {argument['key']!r}")
            if argument["kind"] not in VALUE_KINDS:
                raise ValueError(f"base catalog: {name}.{argument['key']} has unknown kind {argument['kind']!r}")
            keys.add(argument["key"])
            arguments.append(
                BaseArgument(
                    key=argument["key"],
                    kind=argument["kind"],
                    required=bool(argument.get("required", True)),
                    description=argument.get("description"),
                )
            )
        operations.append(
            BaseOperation(
                name=name,
                returns=entry["returns"],
                arguments=tuple(arguments),
                description=entry.get("description"),
            )
        )
    if raw["name"] != BASE_CATALOG_NAME:
        raise ValueError(f"base catalog: unexpected name {raw['name']!r}")
    return BaseCatalog(
        name=raw["name"],
        version=int(raw["version"]),
        operations=tuple(operations),
        description=raw.get("description"),
    )


@functools.lru_cache(maxsize=1)
def load_base_catalog() -> BaseCatalog:
    """The vendored manifest, parsed and validated (cached)."""
    text = resources.files(__package__).joinpath("base_v1.json").read_text(encoding="utf-8")
    return _parse(json.loads(text))


@functools.lru_cache(maxsize=1)
def base_operations() -> Mapping[str, BaseOperation]:
    """Base operations by name."""
    return {operation.name: operation for operation in load_base_catalog().operations}


def base_operation(name: str) -> BaseOperation | None:
    """The base operation called ``name``, or ``None`` if it is not a base operation."""
    return base_operations().get(name)


def is_base_operation(name: str) -> bool:
    """Whether ``name`` is provided by the base catalog."""
    return name in base_operations()
