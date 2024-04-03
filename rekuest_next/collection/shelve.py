from pydantic import BaseModel, Field
from typing import Dict, Any
import contextvars
import uuid

current_shelve = contextvars.ContextVar("current_shelve", default=None)
GLOBAL_SHELVE = None


def get_default_definition_registry():
    global GLOBAL_SHELVE
    if GLOBAL_SHELVE is None:
        GLOBAL_SHELVE = Shelve()
    return GLOBAL_SHELVE


def get_current_shelve(allow_global=True):
    return current_shelve.get(get_default_definition_registry())


class Shelve(BaseModel):
    store: Dict[str, Any] = Field(default_factory=dict)
    free_on_exit: bool = False

    async def aput(self, data: Any):
        """
        Put data in the store.

        :param key: The key to store the data under.
        :param data: The data to store.
        :return: None
        """
        key = str(uuid.uuid4())
        self.store[key] = data
        return key

    async def aget(self, key: str):
        return self.store[key]

    async def adelete(self, key: str):
        del self.store[key]

    async def __aenter__(self):
        self._token = current_shelve.set(self)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.free_on_exit:
            # Freeing the store on exit is useful for testing.
            self.store.clear()

        current_shelve.set(
            None
        )  # should be self._token but that gives an incorrect loop error
        return False
