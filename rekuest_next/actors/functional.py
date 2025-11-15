"""Functional actors for rekuest_next"""

import logging
from concurrent.futures import ThreadPoolExecutor
import sys
from typing import Any, AsyncGenerator, Callable, Dict, List, Self
from koil.helpers import iterate_spawned, run_spawned  # type: ignore
from pydantic import BaseModel, Field
from rekuest_next.actors.base import SerializingActor
from rekuest_next.messages import Assign
from rekuest_next.structures.serialization.actor import expand_inputs, shrink_outputs
from rekuest_next.actors.helper import AssignmentHelper
from rekuest_next.structures.errors import SerializationError
from rekuest_next import messages
from rekuest_next.actors.debug import capture_to_list

logger = logging.getLogger(__name__)


async def async_none_provide(self: "SerializingActor") -> None:
    """Do nothing on provide"""
    return None


async def async_none_unprovide() -> None:
    """Do nothing on unprovide"""
    return None


class FunctionalActor(BaseModel):
    """The based class for all composable functional"

    Functional actors are actors that are based on a function, that
    can be passed on to the actor.
    """

    assign: Callable[..., Any]


class AsyncFuncActor(SerializingActor):
    """The base class for all async functional actors

    Async functional actors are actors that are based on a function, that
    can be passed on to the actor.
    """

    async def assign(self: Self, **kwargs: Dict[str, Any]) -> Any:  # noqa: ANN401
        """This method should be implemented by the actor"""
        raise NotImplementedError("This method should be implemented by the actor")

    async def _assign_func(self: Self, **kwargs: Dict[str, Any]) -> Any:  # noqa: ANN401
        """This is a wrapper for the assign function to be used in the actor
        It should allow to inject some additional logic to the assign function"""
        returns = await self.assign(**kwargs)
        return returns

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

        async with self.sync:
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

            context_kwargs, state_kwargs = await self.aget_locals()

            params: Dict[str, Any] = {
                **input_kwargs,
                **context_kwargs,
                **state_kwargs,
            }

            logs = []

            try:
                async with capture_to_list(logs, self.agent, assignment):
                    async with AssignmentHelper(assignment=assignment, actor=self):
                        returns = await self._assign_func(**params)

                try:
                    returns = await shrink_outputs(
                        self.definition,
                        returns,
                        structure_registry=self.structure_registry,
                        shelver=self.agent,
                        skip_shrinking=not self.shrink_outputs,
                    )
                except SerializationError as ex:
                    logger.critical("Output serialization error", exc_info=True)
                    await self.asend(
                        message=messages.ErrorEvent(
                            assignation=assignment.assignation,
                            error=str(ex),
                        )
                    )
                    return

                await self.async_locals(state_kwargs)

                if assignment.capture:
                    output = "".join(logs)
                    await self.asend(
                        message=messages.LogEvent(
                            assignation=assignment.assignation,
                            message=output,
                            level="INFO",
                        )
                    )

                await self.asend(
                    message=messages.YieldEvent(
                        assignation=assignment.assignation,
                        returns=returns,
                    )
                )

                await self.asend(
                    message=messages.DoneEvent(
                        assignation=assignment.assignation,
                    )
                )

            except (AssertionError, Exception) as ex:
                if assignment.capture:
                    output = "".join(logs)
                    await self.asend(
                        message=messages.LogEvent(
                            assignation=assignment.assignation,
                            message=output,
                            level="INFO",
                        )
                    )

                logger.critical("Assignation error", exc_info=True)
                await self.asend(
                    message=messages.CriticalEvent(
                        assignation=assignment.assignation,
                        error=str(ex),
                    )
                )
                return


class AsyncGenActor(SerializingActor):
    """The base class for all async generator functional actors"""

    async def assign(self, **kwargs: Dict[str, Any]) -> AsyncGenerator[Any, None]:
        """This method should be implemented by the actor"""

        raise NotImplementedError("This method should be implemented by the actor")
        yield None  # type: ignore[unreachable]

    async def _yield_func(self, **kwargs: Dict[str, Any]) -> AsyncGenerator[Any, None]:
        async for returns in self.assign(**kwargs):
            yield returns

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

        async with self.sync:
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

            context_kwargs, state_kwargs = await self.aget_locals()

            params: Dict[str, Any] = {
                **input_kwargs,
                **context_kwargs,
                **state_kwargs,
            }

            logs: List[str] = []

            try:
                async with capture_to_list(logs, self.agent, assignment):
                    async with AssignmentHelper(assignment=assignment, actor=self):
                        async for returns in self._yield_func(**params):
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

                if logs and assignment.capture:
                    output = "".join(logs)
                    await self.asend(
                        message=messages.LogEvent(
                            assignation=assignment.assignation,
                            message=output,
                            level="INFO",
                        )
                    )

                await self.asend(
                    message=messages.DoneEvent(
                        assignation=assignment.assignation,
                    )
                )

            except (AssertionError, Exception) as ex:
                if logs and assignment.capture:
                    output = "".join(logs)
                    await self.asend(
                        message=messages.LogEvent(
                            assignation=assignment.assignation,
                            message=output,
                            level="INFO",
                        )
                    )

                logger.critical("Assignation error", exc_info=True)
                await self.asend(
                    message=messages.CriticalEvent(
                        assignation=assignment.assignation,
                        error=str(ex),
                    )
                )
                return


class FunctionalFuncActor(FunctionalActor, AsyncFuncActor):
    """A functional actor that is composable with
    a function"""


class FunctionalGenActor(FunctionalActor, AsyncGenActor):
    """A functional stream actor that is composable with
    a function"""


class ThreadedFuncActor(AsyncFuncActor):
    """A functional actrot that runs assignmed in a thread pool"""

    executor: ThreadPoolExecutor = Field(default_factory=lambda: ThreadPoolExecutor(1))

    async def _assign_func(self, **kwargs: Dict[str, Any]) -> Any:  # noqa: ANN401
        """This is a wrapper for the assign function to be used in the actor
        It should allow to inject some additional logic to the assign function"""
        # run the function in a thread pool
        returns = await run_spawned(
            self.assign,
            **kwargs,  # type: ignore[no-untyped-call]
        )
        return returns


class ThreadedGenActor(AsyncGenActor):
    """A functional stream actor that runs assigned in a thread pool"""

    executor: ThreadPoolExecutor = Field(default_factory=lambda: ThreadPoolExecutor(4))

    async def _yield_func(self, **kwargs: Dict[str, Any]) -> AsyncGenerator[Any, None]:
        async for returns in iterate_spawned(  # type: ignore
            self.assign,  # type: ignore[no-untyped-call]
            **kwargs,
        ):
            yield returns


class FunctionalThreadedFuncActor(FunctionalActor, ThreadedFuncActor):
    """A composable functional actor that runs assigned in a thread pool"""


class FunctionalThreadedGenActor(FunctionalActor, ThreadedGenActor):
    """A composable functional stream actor that runs assigned in a thread pool"""


class FunctionalAsyncFuncActor(FunctionalActor, AsyncFuncActor):
    """A composable funcitonal actor that is async"""


class FunctionalAsyncGenActor(FunctionalActor, AsyncGenActor):
    """A composable functional stream actor that is async"""
