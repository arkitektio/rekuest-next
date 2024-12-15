from abc import abstractmethod

from pydantic import ConfigDict

from rekuest_next.messages import OutMessage

from koil.composition import KoiledModel
from koil.types import Contextual
from .types import TransportCallbacks


class AgentTransport(KoiledModel):
    """Agent Transport

    A Transport is a means of communicating with an Agent. It is responsible for sending
    and receiving messages from the backend. It needs to implement the following methods:

    list_provision: Getting the list of active provisions from the backend. (depends on the backend)
    list_assignation: Getting the list of active assignations from the backend. (depends on the backend)

    change_assignation: Changing the status of an assignation. (depends on the backend)
    change_provision: Changing the status of an provision. (depends on the backend)

    broadcast: Configuring the callbacks for the transport on new assignation, unassignation provision and unprovison.

    if it is a stateful connection it can also implement the following methods:

    aconnect
    adisconnect

    """

    _callback: Contextual[TransportCallbacks]
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def connected(self):
        return NotImplementedError("Implement this method")

    @abstractmethod
    async def log_event(self, event: OutMessage):
        raise NotImplementedError("This is an abstract Base Class")

    def set_callback(self, callback: TransportCallbacks):
        self._callback = callback

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

