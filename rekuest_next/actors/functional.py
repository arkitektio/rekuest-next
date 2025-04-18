import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable
from koil.helpers import iterate_spawned, run_spawned
from pydantic import BaseModel, Field
from rekuest_next.actors.base import SerializingActor
from rekuest_next.messages import Assign
from rekuest_next.api.schema import AssignationEventKind
from rekuest_next.structures.serialization.actor import expand_inputs, shrink_outputs
from rekuest_next.actors.helper import AssignmentHelper

from rekuest_next.collection.collector import Collector
from rekuest_next.actors.transport.types import AssignTransport
from rekuest_next.structures.parse_collectables import parse_collectable
from rekuest_next.structures.errors import SerializationError
from rekuest_next import messages
logger = logging.getLogger(__name__)


async def async_none_provide():
    """Do nothing on provide"""
    return None


async def async_none_unprovide():
    """Do nothing on unprovide"""
    return None


class FunctionalActor(BaseModel):
    assign: Callable[..., Any]


class AsyncFuncActor(SerializingActor):
    
    async def assign(self, **kwargs):
        """This method should be implemented by the actor"""
        raise NotImplementedError("This method should be implemented by the actor")
    
    async def _assign_func(self, **kwargs):
        returns = await self.assign(**kwargs)
        return returns
    
    async def on_assign(
        self,
        assignment: Assign,
    ):

        await self.asend(
            message=messages.ProgressEvent(
                assignation=assignment.assignation,
                percentage=0,
                messages="Queued for running",
            )
        )

        async with self.sync:
            try:
                
                await self.asend(
                    message=messages.ProgressEvent(
                        assignation=assignment.assignation,
                        percentage=0,
                        messages="Queued for running",
                    )
                )

                params = await expand_inputs(
                    self.definition,
                    assignment.args,
                    structure_registry=self.structure_registry,
                    skip_expanding=not self.expand_inputs,
                )

                params = await self.add_local_variables(params)

                await self.asend(
                    message=messages.ProgressEvent(
                        assignation=assignment.assignation,
                        percentage=0,
                        messages="Queued for running",
                    )
                )

                async with AssignmentHelper(
                    assignment=assignment, actor=self
                ):
                    returns = await self._assign_func(**params)

                returns = await shrink_outputs(
                    self.definition,
                    returns,
                    structure_registry=self.structure_registry,
                    skip_shrinking=not self.shrink_outputs,
                )

                self.collector.register(
                    assignment, parse_collectable(self.definition, returns)
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

            except SerializationError as ex:
                logger.critical("Assignation error", exc_info=True)
                await self.asend(
                    message=messages.ErrorEvent(
                        assignation=assignment.assignation,
                        error=str(ex),
                    )
                )

            except AssertionError as ex:
                logger.critical("Assignation error", exc_info=True)
                await self.asend(
                    message=messages.CriticalEvent(
                        assignation=assignment.assignation,
                        error=str(ex),
                    )
                )
                
            except Exception as ex:
                logger.critical("Assignation error", exc_info=True)
                await self.asend(
                    message=messages.CriticalEvent(
                        assignation=assignment.assignation,
                        error=str(ex),
                    )
                )


class AsyncGenActor(SerializingActor):
    
    async def assign(self, **kwargs):
        """This method should be implemented by the actor"""
        raise NotImplementedError("This method should be implemented by the actor")
    
    
    async def _yield_func(self, **kwargs):
        async for returns in self.assign(**kwargs):
            yield returns
    
    
    async def on_assign(
        self,
        assignment: Assign,
    ):
        await self.asend(
                    message=messages.ProgressEvent(
                assignation=assignment.assignation,
                percentage=0,
                messages="Queued for running",
            )
        )

        async with self.sync:
            try:
                params = await expand_inputs(
                    self.definition,
                    assignment.args,
                    structure_registry=self.structure_registry,
                    skip_expanding=not self.expand_inputs,
                )

                params = await self.add_local_variables(params)
                
                
                await self.asend(
                    message=messages.ProgressEvent(
                        assignation=assignment.assignation,
                        percentage=0,
                        messages="Queued for running",
                    )
                )

                async with AssignmentHelper(
                    assignment=assignment, actor=self,
                ):
                    async for returns in self._yield_func(**params):
                        returns = await shrink_outputs(
                            self.definition,
                            returns,
                            structure_registry=self.structure_registry,
                            skip_shrinking=not self.shrink_outputs,
                        )

                        self.collector.register(
                            assignment, parse_collectable(self.definition, returns)
                        )

                        await self.asend(
                            message=messages.YieldEvent(
                                assignation=assignment.assignation,
                                returns=returns,
                                messages="Queued for running",
                            )
                        )

                await self.asend(
                    message=messages.DoneEvent(
                        assignation=assignment.assignation,
                        messages="Queued for running",
                    )
                )

            
            except SerializationError as ex:
                logger.critical("Assignation error", exc_info=True)
                await self.asend(
                    message=messages.ErrorEvent(
                        assignation=assignment.assignation,
                        error=str(ex),
                    )
                )

            except AssertionError as ex:
                logger.critical("Assignation error", exc_info=True)
                await self.asend(
                    message=messages.CriticalEvent(
                        assignation=assignment.assignation,
                        error=str(ex),
                    )
                )
                
            except Exception as ex:
                logger.critical("Assignation error", exc_info=True)
                await self.asend(
                    message=messages.CriticalEvent(
                        assignation=assignment.assignation,
                        error=str(ex),
                    )
                )


class FunctionalFuncActor(FunctionalActor, AsyncFuncActor):
    async def progress(self, value, percentage):
        await self._progress(value, percentage)


class FunctionalGenActor(FunctionalActor, AsyncGenActor):
    async def progress(self, value, percentage):
        await self._progress(value, percentage)


class ThreadedFuncActor(AsyncFuncActor):
    executor: ThreadPoolExecutor = Field(default_factory=lambda: ThreadPoolExecutor(1))
    
    
    async def _assign_func(self, **kwargs):
        returns = await run_spawned(
            self.assign, **kwargs, executor=self.executor, pass_context=True
        )
        return returns



class ThreadedGenActor(AsyncGenActor):
    executor: ThreadPoolExecutor = Field(default_factory=lambda: ThreadPoolExecutor(4))

    async def _yield_func(self, **kwargs):
        async for returns in iterate_spawned(
            self.assign, **kwargs, executor=self.executor, pass_context=True
        ):
            yield returns



class FunctionalThreadedFuncActor(FunctionalActor, ThreadedFuncActor):
    async def progress(self, value, percentage):
        await self._progress(value, percentage)


class FunctionalThreadedGenActor(FunctionalActor, ThreadedGenActor):
    async def progress(self, value, percentage):
        await self._progress(value, percentage)

class FunctionalAsyncFuncActor(FunctionalActor, AsyncFuncActor):
    async def progress(self, value, percentage):
        await self._progress(value, percentage)
        
class FunctionalAsyncGenActor(FunctionalActor, AsyncGenActor):
    async def progress(self, value, percentage):
        await self._progress(value, percentage)