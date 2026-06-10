"""Functional actors for rekuest_next"""

import logging
from typing import Any, AsyncGenerator, Callable, Dict, List, Self
from koil.helpers import iterate_spawned, run_spawned  # type: ignore
from rekuest_next.actors.base import SerializingActor
from rekuest_next.messages import Assign
from rekuest_next.structures.serialization.actor import expand_inputs, shrink_outputs
from rekuest_next.actors.helper import AssignmentHelper
from rekuest_next.structures.errors import SerializationError
from rekuest_next import messages
from rekuest_next.actors.debug import capture_to_list

logger = logging.getLogger(__name__)


class FunctionalActorBase(SerializingActor):
    """The base class for all functional actors.

    Functional actors wrap a plain callable (``assign``) and run it through a
    single assignment pipeline: expand inputs, inject state/context/dependency
    locals, execute, shrink each result, and publish Yield/Done events.

    Subclasses only define :meth:`aiterate_results` — how the wrapped callable
    is invoked and how its results are iterated.
    """

    assign: Callable[..., Any]

    def aiterate_results(
        self: Self, **params: Dict[str, Any]
    ) -> AsyncGenerator[Any, None]:
        """Invoke the wrapped callable and yield its result(s)."""
        raise NotImplementedError("This method should be implemented by the actor")

    async def on_assign(
        self: Self,
        assignment: Assign,
    ) -> None:
        """This method is called when the actor is assigned to a task"""

        await self.asend(
            message=messages.ProgressEvent(
                assignation=assignment.assignation,
                progress=0,
                message="Queued for running",
            )
        )

        async with self.sync_context(assignment.assignation, assignment.interface):
            try:
                input_kwargs = await expand_inputs(
                    self.definition,
                    assignment.args,
                    structure_registry=self.structure_registry,
                    shelver=self.agent,
                    skip_expanding=not self.expand_inputs,
                )
            except Exception as ex:
                logger.critical("Input serialization error", exc_info=True)
                await self.asend(
                    message=messages.ErrorEvent(
                        assignation=assignment.assignation,
                        error=str(ex),
                    )
                )
                return

            context_kwargs, state_kwargs, dependency_kwargs = await self.aget_locals()

            params: Dict[str, Any] = {
                **input_kwargs,
                **context_kwargs,
                **state_kwargs,
                **dependency_kwargs,
            }

            logs: List[str] = []

            async def aflush_captured_logs() -> None:
                if logs and assignment.capture:
                    await self.asend(
                        message=messages.LogEvent(
                            assignation=assignment.assignation,
                            message="".join(logs),
                            level="INFO",
                        )
                    )

            try:
                async with capture_to_list(logs, self.agent, assignment):
                    async with AssignmentHelper(assignment=assignment, actor=self):
                        async for returns in self.aiterate_results(**params):
                            try:
                                returns = await shrink_outputs(
                                    self.definition,
                                    returns,
                                    structure_registry=self.structure_registry,
                                    shelver=self.agent,
                                    skip_shrinking=not self.shrink_outputs,
                                )
                            except SerializationError as ex:
                                logger.critical(
                                    "Output serialization error", exc_info=True
                                )
                                await self.asend(
                                    message=messages.ErrorEvent(
                                        assignation=assignment.assignation,
                                        error=str(ex),
                                    )
                                )
                                return

                            await self.asend(
                                message=messages.YieldEvent(
                                    assignation=assignment.assignation,
                                    returns=returns,
                                )
                            )

                            await self.async_locals(state_kwargs)

                await aflush_captured_logs()

                await self.asend(
                    message=messages.DoneEvent(
                        assignation=assignment.assignation,
                    )
                )

            except Exception as ex:
                await aflush_captured_logs()

                logger.critical("Assignation error", exc_info=True)
                await self.asend(
                    message=messages.CriticalEvent(
                        assignation=assignment.assignation,
                        error=str(ex),
                    )
                )
                return


class FunctionalFuncActor(FunctionalActorBase):
    """A functional actor wrapping an async function."""

    async def aiterate_results(
        self: Self, **params: Dict[str, Any]
    ) -> AsyncGenerator[Any, None]:
        """Await the wrapped coroutine function and yield its single result."""
        yield await self.assign(**params)


class FunctionalGenActor(FunctionalActorBase):
    """A functional stream actor wrapping an async generator function."""

    async def aiterate_results(
        self: Self, **params: Dict[str, Any]
    ) -> AsyncGenerator[Any, None]:
        """Iterate the wrapped async generator."""
        async for returns in self.assign(**params):
            yield returns


class FunctionalThreadedFuncActor(FunctionalActorBase):
    """A functional actor running a sync function in a worker thread."""

    async def aiterate_results(
        self: Self, **params: Dict[str, Any]
    ) -> AsyncGenerator[Any, None]:
        """Run the wrapped sync function in a thread and yield its result."""
        yield await run_spawned(self.assign, **params)


class FunctionalThreadedGenActor(FunctionalActorBase):
    """A functional stream actor running a sync generator in a worker thread."""

    async def aiterate_results(
        self: Self, **params: Dict[str, Any]
    ) -> AsyncGenerator[Any, None]:
        """Iterate the wrapped sync generator from a worker thread."""
        async for returns in iterate_spawned(self.assign, **params):
            yield returns
