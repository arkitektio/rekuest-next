from ast import ParamSpec
from typing import Callable, TypeVar, Awaitable, List
import asyncio
from rekuest_next.actors.context import aprogress

T = TypeVar("T")


async def iterate_with_progress(
    future_builder: Callable[[int], Awaitable[T]],
    iterations: int,
) -> List[T]:
    """Runs multiple async tasks while tracking progress.

    Args:
        future_builder (Callable[[int], Awaitable[T]]): A function that takes an integer
            and returns an awaitable that produces a result of type T.
        iterations (int): The number of iterations to run.
    """
    completed = 0

    async def wrapper(i: int) -> T:
        nonlocal completed
        result = await future_builder(i)
        completed += 1
        try:
            await aprogress(100 * completed / iterations)
        except Exception as e:
            pass
        return result

    tasks = [asyncio.create_task(wrapper(i)) for i in range(iterations)]
    return await asyncio.gather(*tasks)


P = ParamSpec("P")


async def gather_with_progress(
    futures: List[Awaitable[T]],
) -> List[T]:
    """Ghathers multiple async tasks while tracking progress.

    Args:
        future_builder (Callable[[int], Awaitable[T]]): A function that takes an integer
            and returns an awaitable that produces a result of type T.
        iterations (int): The number of iterations to run.
    """
    completed = 0
    iterations = len(futures)

    async def wrapper(i: int) -> T:
        nonlocal completed
        result = await future_builder(i)
        completed += 1
        try:
            await aprogress(100 * completed / iterations)
        except Exception as e:
            pass
        return result

    tasks = [asyncio.create_task(wrapper(i)) for i in range(iterations)]
    return await asyncio.gather(*tasks)
