from typing import Protocol, Any
import asyncio

from koil import unkoil


class ProxyHolder(Protocol):

    async def aget_state(self, state_key: str, attribute: str): ...

    async def aset_state(self, state_key: str, attribute: str, value: Any): ...


class AGetProperty:

    def __init__(self, proxy_holder, state_key, attribute):
        self.state_key = state_key
        self.attribute = attribute
        self.proxy_holder = proxy_holder

    async def aget(self):
        return await self.proxy_holder.aget_state(self.state_key, self.attribute)

    async def aset(self, value):
        return await self.proxy_holder.aset_state(self.state_key, self.attribute, value)


class StateProxy:

    def __init__(self, proxy_holder: ProxyHolder, state_key: str):
        self.proxy_holder = proxy_holder
        self.state_key = state_key

    async def aget(self, attribute):
        return await self.proxy_holder.aget_state(self.state_key, attribute)

    async def aset(self, attribute, value):
        return await self.proxy_holder.aset_state(self.state_key, attribute, value)

    def __getattr__(self, name):
        if name in ["proxy_holder", "state_key", "aget", "aset"]:
            return super().__getattr__(name)
        # Check if runnning in async context
        try:
            asyncio.get_running_loop()
            return AGetProperty(self.proxy_holder, self.state_key, name)
        except RuntimeError:
            return unkoil(self.aget, name)

    def __setattr__(self, name, value):
        if name in ["proxy_holder", "state_key", "aget", "aset"]:
            super().__setattr__(name, value)
            return
        # Check if runnning in async context
        try:
            asyncio.get_running_loop()
            raise AttributeError(
                f"You are running async you need to use aset e.g `await this_variable_name.{name}.aset(10)`"
            )
        except RuntimeError:
            return unkoil(self.aset, name, value)
