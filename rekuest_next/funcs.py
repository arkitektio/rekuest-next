"""Functions for executing queries and mutations using Rekuest Next and Rath.

This function hook into the api funciton that are autogenerated by turms and
allow you to execute queries and mutations using thre rekuest-rath client.

"""

from typing import Any, Dict, Generator, AsyncGenerator, Type
from rekuest_next.rath import RekuestNextRath, current_rekuest_next_rath
from koil import unkoil, unkoil_gen
from rath.turms.funcs import TOperation
from .errors import NoRekuestRathFoundError


def execute(
    operation: Type[TOperation],
    variables: Dict[str, Any],
    rath: RekuestNextRath | None = None,
) -> TOperation:
    """Executes a query or mutation using rath in a blocking way."""
    return unkoil(aexecute, operation, variables, rath)


async def aexecute(
    operation: Type[TOperation],
    variables: Dict[str, Any],
    rath: RekuestNextRath | None = None,
) -> TOperation:
    """Executes a query or mutation using rath in a non-blocking way."""
    rath = rath or current_rekuest_next_rath.get()
    if not rath:
        raise NoRekuestRathFoundError(
            "No rath client found in context. Please provide a rath client."
        )

    x = await rath.aquery(
        operation.Meta.document,
        operation.Arguments(**variables).model_dump(by_alias=True, exclude_unset=True),
    )
    return operation(**x.data)


def subscribe(
    operation: Type[TOperation],
    variables: Dict[str, Any],
    rath: RekuestNextRath | None = None,
) -> Generator[TOperation, None, None]:
    """Subscribes to a query or mutation using rath in a blocking way."""
    return unkoil_gen(asubscribe, operation, variables, rath)


async def asubscribe(
    operation: Type[TOperation],
    variables: Dict[str, Any],
    rath: RekuestNextRath | None = None,
) -> AsyncGenerator[TOperation, None]:
    """Subscribes to a query or mutation using rath in a non-blocking way."""
    rath = rath or current_rekuest_next_rath.get()
    if not rath:
        raise NoRekuestRathFoundError(
            "No rath client found in context. Please provide a rath client."
        )

    async for event in rath.asubscribe(
        operation.Meta.document,
        operation.Arguments(**variables).model_dump(by_alias=True),
    ):
        yield operation(**event.data)
