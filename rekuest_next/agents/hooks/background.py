"""Hooks for the agent"""

import inspect
from typing import (
    Any,
    TypeVar,
    cast,
    overload,
)
from collections.abc import Callable
import asyncio

from koil.bridge import run_threaded
from rekuest_next.state.publish import StateHolder
from rekuest_next.agents.hooks.registry import (
    HooksRegistry,
    get_default_hook_registry,
)
from rekuest_next.agents.hooks.variables import WithVariables
from rekuest_next.protocols import (
    BackgroundFunction,
    ThreadedBackgroundFunction,
    AsyncBackgroundFunction,
)
from rekuest_next.state.publish import direct_publishing


class BackgroundWithVariables(WithVariables):
    hook_kind = "Background"


class WrappedBackgroundTask(BackgroundWithVariables):
    """Background task that runs in the event loop"""

    def __init__(self, func: AsyncBackgroundFunction) -> None:
        """Initialize the background task
        Args:
            func (Callable): The function to run in the background async
        """
        super().__init__(func)

    async def arun(
        self,
        agent: StateHolder,
        contexts: dict[str, Any],
        states: dict[str, Any],
        app_context: Any = None,  # noqa: ANN401
    ) -> None:
        """Run the background task in the event loop"""
        kwargs = self.get_kwargs(contexts, states, app_context)
        with direct_publishing(agent):
            return await self.func(**kwargs)


class WrappedThreadedBackgroundTask(BackgroundWithVariables):
    """Background task that runs in a thread pool"""

    def __init__(self, func: ThreadedBackgroundFunction) -> None:
        """Initialize the background task
        Args:
            func (Callable): The function to run in the background
        """
        super().__init__(func)

    def run_with_publishing(self, agent: StateHolder, **kwargs: Any) -> None:
        with direct_publishing(agent):
            return self.func(**kwargs)

    async def arun(
        self,
        agent: StateHolder,
        contexts: dict[str, Any],
        states: dict[str, Any],
        app_context: Any = None,  # noqa: ANN401
    ) -> None:
        """Run the background task in a thread pool"""
        kwargs = self.get_kwargs(contexts, states, app_context)
        return await run_threaded(
            self.run_with_publishing,
            agent,
            **kwargs,  # type: ignore[arg-type]
        )


TBackground = TypeVar("TBackground", bound=BackgroundFunction)


@overload
def background(*args: TBackground) -> TBackground: ...


@overload
def background(
    *, name: str | None = None, registry: HooksRegistry | None = None
) -> Callable[[TBackground], TBackground]: ...


@overload
def background(
    *args: TBackground,
    name: str | None = None,
    registry: HooksRegistry | None = None,
) -> TBackground | Callable[[TBackground], TBackground]: ...


def background(  # noqa: ANN201
    *args: TBackground,
    name: str | None = None,
    registry: HooksRegistry | None = None,
) -> TBackground | Callable[[TBackground], TBackground]:
    """Register a background task on the selected hook registry.

    Background tasks start with the agent and keep running until shutdown. The
    task signature is inspected for state, context, and app-context dependencies
    so the runtime can inject matching values when the task is launched.

    Async background tasks run in the event loop. Synchronous ones are wrapped
    in ``WrappedThreadedBackgroundTask`` and executed through ``run_threaded``.
    Both variants run inside ``direct_publishing`` so state mutations are
    propagated immediately.

    Args:
        *args: Background function to register when used as ``@background``
            without parentheses.
        name: Explicit registry key. Defaults to the function name.
        registry: Hook registry to populate. Defaults to the global hook
            registry.

    Returns:
        The original function, or a decorator configured with the provided
        metadata.

    Raises:
        ValueError: If more than one function is passed at once.

    Examples:
        Register a long-running async background loop::

            @background
            async def heartbeat(state: MyState) -> None:
                while True:
                    state.counter += 1
                    await asyncio.sleep(1)
    """

    if len(args) > 1:
        raise ValueError("You can only register one function at a time.")
    if len(args) == 1:
        function = args[0]
        registry = registry or get_default_hook_registry()
        name = name or function.__name__
        if asyncio.iscoroutinefunction(function):
            a = cast(AsyncBackgroundFunction, function)
            registry.register_background(name, WrappedBackgroundTask(a))
        else:
            assert inspect.isfunction(function) or inspect.ismethod(function), (
                "Function must be a async function or a sync function"
            )
            t = cast(ThreadedBackgroundFunction, function)
            registry.register_background(name, WrappedThreadedBackgroundTask(t))

        return cast(TBackground, function)

    else:

        def decorator(function: TBackground) -> TBackground:
            return cast(TBackground, background(function, name=name, registry=registry))

        return decorator
