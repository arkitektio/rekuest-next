"""Functions for testing"""

import asyncio
from collections.abc import Generator
from .structures import SecondObject, SecondSerializableObject, SerializableObject
from annotated_types import Le, Predicate, Gt, Len
from rekuest_next.structures.model import model
from rekuest_next.api.schema import AssignWidgetInput, AssignWidgetKind


from typing import Annotated


def null_function(x: int | None) -> None:
    """Karl

    Karl takes a a representation and does magic stuff

    Args:
        rep (str): Nougat
        name (str, optional): Bugat

    Returns:
        Representation: The Returned Representation
    """
    return None


def plain_basic_function(rep: str, name: str | None = None) -> str:
    """Karl

    Karl takes a a representation and does magic stuff

    Args:
        rep (str): Nougat
        name (str, optional): Bugat

    Returns:
        Representation: The Returned Representation
    """
    return "tested"


def plain_structure_function(
    rep: SerializableObject, name: SerializableObject | None = None
) -> SecondSerializableObject:
    """Karl

    Karl takes a a representation and does magic stuff

    Args:
        rep (SerializableObject): Nougat
        name (SerializableObject, optional): Bugat

    Returns:
        SecondSerializableObject: The Returned Representation
    """
    return SecondSerializableObject("tested")


def union_structure_function(
    rep: SerializableObject | SecondSerializableObject,
) -> SerializableObject | SecondSerializableObject:
    """Karl

    Karl takes a a representation and does magic stuff

    Args:
        rep (SerializableObject): Nougat
        name (SerializableObject, optional): Bugat

    Returns:
        SecondSerializableObject: The Returned Representation
    """
    return (
        SerializableObject(number=6)
        if isinstance(rep, SerializableObject)
        else SecondSerializableObject("tested")
    )


def basic_union_function(
    rep: int | SerializableObject,
) -> int | SerializableObject:
    """A union mixing a basic type with a structure.

    Exercises the case that used to break: a bare ``int`` member of a union has
    to round-trip through the tagged ``{"__use", "__value"}`` wire format.

    Args:
        rep (Union[int, SerializableObject]): Either a plain int or a structure.

    Returns:
        Union[int, SerializableObject]: The same value back.
    """
    return rep


def numeric_union_function(rep: int | float) -> int | float:
    """A union of two numeric types whose JSON encodings collapse.

    Used to prove the ``use`` index is authoritative on expand: an int on the
    wire tagged as the float arm must expand to a float.

    Args:
        rep (Union[int, float]): An int or a float.

    Returns:
        Union[int, float]: The same value back.
    """
    return rep


def nested_basic_function(
    rep: list[str], nana: dict[str, int], name: str | None = None
) -> tuple[list[str], int]:
    """Structure Karl

    Nananan

    Args:
        rep (List[str]): arg
        rep (List[str]): arg2
        name (str, optional): kwarg. Defaults to None.

    Returns:
        Tuple[List[str], int]: return, return2
    """
    return ["tested"], 6


def nested_structure_function(
    rep: list[SerializableObject], name: dict[str, SerializableObject] | None = None
) -> tuple[str, dict[str, SecondSerializableObject]]:
    """Structured Karl

    Naoinaoainao

    Args:
        rep (List[SerializableObject]): [description]
        name (Dict[str, SerializableObject], optional): [description]. Defaults to None.

    Returns:
        str: [description]
        Dict[str, SecondSerializableObject]: [description]
    """
    return "tested"


def annotated_basic_function(
    rep: Annotated[str, Predicate(str.islower)],
    number: Annotated[str, Le(4), Gt(4)] | None = None,
) -> str:
    """Annotated Karl

    Karl takes a a representation and does magic stuff

    Args:
        rep (str): Nougat
        name (str, optional): Bugat

    Returns:
        Representation: The Returned Representation
    """
    return "tested"


def annotated_nested_structure_function(
    rep: Annotated[str, Predicate(str.islower)],
    number: dict[str, Annotated[list[SecondSerializableObject], Len(3)]] | None = None,
) -> str:
    """Annotated Karl

    Karl takes a a representation and does magic stuff

    Args:
        rep (str): Nougat
        name (str, optional): Bugat

    Returns:
        Representation: The Returned Representation
    """
    return "tested"


def nested_structure_generator(
    rep: list[SecondObject], name: dict[str, SecondObject] | None = None
) -> Generator[tuple[str, dict[str, SecondObject]], None, None]:
    """Structured Karl

    Naoinaoainao

    Args:
        rep (List[SecondObject]): [description]
        name (Dict[str, SerializableObject], optional): [description]. Defaults to None.

    Returns:
        str: [description]
        Dict[str, SecondSerializableObject]: [description]
    """
    yield "tested", {"peter": SecondObject("6")}


async def nested_structure_asyncgenerator(
    rep: list[SecondObject], name: dict[str, SecondObject] | None = None
) -> tuple[str, dict[str, SecondObject]]:  # type: ignore
    """function_with_side_register_async

    Naoinaoainao

    Args:
        rep (List[SecondObject]): [description]
        name (Dict[str, SerializableObject], optional): [description]. Defaults to None.

    Returns:
        str: [description]
        Dict[str, SecondSerializableObject]: [description]
    """
    while True:
        await asyncio.sleep(0.2)
        yield "tested", {"peter": SecondObject(6)}


@model
class Karl:
    """Karl"""

    int: Annotated[int, Gt(3)]
    strucutre: Annotated[SecondObject, AssignWidgetInput(kind=AssignWidgetKind.CUSTOM)]


async def nested_model_with_annotations(karls: list[Karl]) -> list[Karl]:
    """Karl

    Karl takes a a representation and does magic stuff

    Args:
        karls (List[Karl]): Nougat
        name (str, optional): Bugat

    Returns:
        Representation: The Returned Representation
    """
    return "tested"


class LocalizedStructure:
    """Localized structure"""

    def __init__(self, name: str) -> None:
        """Localized structure

        Args:
            name (str): Name of the localized structure
        """
        self.name = name


async def create_localized_structure() -> LocalizedStructure:
    """Create a localized structure

    Returns:
        LocalizedStructure: Localized structure
    """
    return LocalizedStructure("localized_structure")


async def localized_structure_function(rep: LocalizedStructure) -> LocalizedStructure:
    """Localized structure function

    Args:
        rep (LocalizedStructure): Localized structure
        name (LocalizedStructure, optional): Localized structure. Defaults to None.

    Returns:
        LocalizedStructure: Localized structure
    """
    return rep
