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

#: A strategy that invokes the wrapped callable and yields its result(s).
ResultIterator = Callable[..., AsyncGenerator[Any, None]]


class FunctionalActor(SerializingActor):
    """An actor that wraps a plain callable (``assign``).

    Functional actors run the wrapped callable through a single assignment
    pipeline: expand inputs, inject state/context/dependency locals, execute,
    shrink each result, and publish Yield/Done events.

    How the callable is invoked and iterated is supplied as an ``iterator``
    strategy (see :data:`FUNC`, :data:`GEN`, :data:`THREADED_FUNC`,
    :data:`THREADED_GEN`) rather than via subclassing — async vs sync and
    single-value vs generator only differ in that one step.
    """

    assign: Callable[..., Any]
    iterator: "ResultIterator"

    def aiterate_results(
        self: Self, **params: Dict[str, Any]
    ) -> AsyncGenerator[Any, None]:
        """Invoke the wrapped callable and yield its result(s)."""
        return self.iterator(self.assign, **params)

    async def on_assign(
        self: Self,
        assignment: Assign,
    ) -> None:
        """This method is called when the actor is assigned to a task"""

        impl_id = (
            f"implementation '{self.definition.name}' "
            f"(interface={assignment.interface}, action={assignment.action}, "
            f"task={assignment.task})"
        )

        await self.asend(
            message=messages.ProgressEvent(
                task=assignment.task,
                progress=0,
                message="Queued for running",
            )
        )

        async with self.sync_context(assignment.task, assignment.interface):
            try:
                input_kwargs = await expand_inputs(
                    self.definition,
                    assignment.args,
                    structure_registry=self.structure_registry,
                    shelver=self.agent,
                    skip_expanding=not self.expand_inputs,
                )
            except Exception as ex:
                logger.critical(
                    f"Input serialization error in {impl_id}", exc_info=True
                )
                await self.asend(
                    message=messages.ErrorEvent(
                        task=assignment.task,
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
                            task=assignment.task,
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
                                    f"Output serialization error in {impl_id}",
                                    exc_info=True,
                                )
                                await self.asend(
                                    message=messages.ErrorEvent(
                                        task=assignment.task,
                                        error=str(ex),
                                    )
                                )
                                return

                            await self.asend(
                                message=messages.YieldEvent(
                                    task=assignment.task,
                                    returns=returns,
                                )
                            )

                await aflush_captured_logs()

                await self.asend(
                    message=messages.DoneEvent(
                        task=assignment.task,
                    )
                )

            except Exception as ex:
                await aflush_captured_logs()

                logger.critical(f"Task error in {impl_id}", exc_info=True)
                await self.asend(
                    message=messages.CriticalEvent(
                        task=assignment.task,
                        error=str(ex),
                    )
                )
                return


async def _func_iterator(
    assign: Callable[..., Any], **params: Any
) -> AsyncGenerator[Any, None]:
    """Await an async function and yield its single result."""
    yield await assign(**params)


async def _gen_iterator(
    assign: Callable[..., Any], **params: Any
) -> AsyncGenerator[Any, None]:
    """Iterate an async generator function."""
    async for returns in assign(**params):
        yield returns


async def _threaded_func_iterator(
    assign: Callable[..., Any], **params: Any
) -> AsyncGenerator[Any, None]:
    """Run a sync function in a worker thread and yield its result."""
    yield await run_spawned(assign, **params)


async def _threaded_gen_iterator(
    assign: Callable[..., Any], **params: Any
) -> AsyncGenerator[Any, None]:
    """Iterate a sync generator function from a worker thread."""
    async for returns in iterate_spawned(assign, **params):
        yield returns


#: Strategy for an async function.
FUNC: "ResultIterator" = _func_iterator
#: Strategy for an async generator function.
GEN: "ResultIterator" = _gen_iterator
#: Strategy for a sync function (run in a worker thread).
THREADED_FUNC: "ResultIterator" = _threaded_func_iterator
#: Strategy for a sync generator function (run in a worker thread).
THREADED_GEN: "ResultIterator" = _threaded_gen_iterator
