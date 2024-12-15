from typing import Awaitable, Callable

from rekuest_next.messages import OutMessage, ProvisionEvent, AssignationEvent
from pydantic import ConfigDict
from koil.composition import KoiledModel
import logging
from rekuest_next.actors.types import Passport
from rekuest_next.messages import Assign


logger = logging.getLogger(__name__)


class ProxyAssignTransport(KoiledModel):
    assignment: Assign
    on_log: Callable[[OutMessage], Awaitable[None]]
    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def log_event(self, *args, **kwargs):
        await self.on_log(
            AssignationEvent(
                id=self.assignment.id, assignation=self.assignment.assignation, **kwargs
            )
        )  # Forwards assignment up



class ProxyActorTransport(KoiledModel):
    passport: Passport
    on_log_event: Callable[[OutMessage], Awaitable[None]]

    async def log_event(self, **kwargs):
        await self.on_log_event(
            ProvisionEvent(provision=self.passport.provision, **kwargs)
        )

    def spawn(self, assignment: Assign) -> ProxyAssignTransport:
        return ProxyAssignTransport(
            assignment=assignment,
            on_log=self.on_log_event,
        )
