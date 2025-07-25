"""Functions for testing"""

import asyncio
import sys
from typing import Dict, Generator, List, Tuple, Optional, Union
from .structures import SecondObject, SecondSerializableObject, SerializableObject
from annotated_types import Le, Predicate, Gt, Len
from rekuest_next.structures.model import model
from rekuest_next.api.schema import AssignWidgetInput, AssignWidgetKind


if sys.version_info < (3, 9):
    from typing_extensions import Annotated
else:
    from typing import Annotated


def null_function(x: Optional[int]) -> None:
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
    rep: Union[SerializableObject, SecondSerializableObject],
) -> Union[SerializableObject, SecondSerializableObject]:
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


def nested_basic_function(
    rep: List[str], nana: Dict[str, int], name: str | None = None
) -> Tuple[List[str], int]:
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
    rep: List[SerializableObject], name: Dict[str, SerializableObject] | None = None
) -> Tuple[str, Dict[str, SecondSerializableObject]]:
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
    number: Dict[str, Annotated[List[SecondSerializableObject], Len(3)]] | None = None,
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
    rep: List[SecondObject], name: Dict[str, SecondObject] | None = None
) -> Generator[Tuple[str, Dict[str, SecondObject]], None, None]:
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
    rep: List[SecondObject], name: Dict[str, SecondObject] | None = None
) -> Tuple[str, Dict[str, SecondObject]]:  # type: ignore
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


async def nested_model_with_annotations(karls: List[Karl]) -> List[Karl]:
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
