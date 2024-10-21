from rekuest_next.rath import RekuestNextRath, current_rekuest_next_rath
from koil import unkoil
from koil.helpers import unkoil_gen


def execute(operation, variables, rath: RekuestNextRath = None):
    return unkoil(aexecute, operation, variables, rath)


async def aexecute(operation, variables, rath: RekuestNextRath = None):
    rath = rath or current_rekuest_next_rath.get()
    x = await rath.aquery(
        operation.Meta.document,
        operation.Arguments(**variables).model_dump(by_alias=True),
    )
    return operation(**x.data)


def subscribe(operation, variables, rath: RekuestNextRath = None):
    """is subscribing"""
    return unkoil_gen(asubscribe, operation, variables, rath)


async def asubscribe(operation, variables, rath: RekuestNextRath = None):
    rath = rath or current_rekuest_next_rath.get()
    async for event in rath.asubscribe(
        operation.Meta.document,
        operation.Arguments(**variables).model_dump(by_alias=True),
    ):
        yield operation(**event.data)
