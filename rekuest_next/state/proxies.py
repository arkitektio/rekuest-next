"""State proxies for the rekuest_next library."""

from typing import Dict, Protocol, Any
import asyncio

from koil import unkoil


class ProxyHolder(Protocol):
    """A protocol for the proxy holder that is used to get and set states."""

    async def aget_state(self, state_key: str, attribute: str) -> Dict[str, Any]:
        """Get the state of the actor. This method will get the state of the"""
        ...

    async def aset_state(self, state_key: str, attribute: str, value: Dict[str, Any]) -> None:
        """Set the state of the actor. This method will set the state of the"""
        ...


class AGetProperty:
    """A class to get the state of the actor. This class is used to get the state of the actor"""

    def __init__(self, proxy_holder: ProxyHolder, state_key: str, attribute: str) -> None:
        """Initialize the class with the proxy holder and the state key"""

        self.state_key = state_key
        self.attribute = attribute
        self.proxy_holder = proxy_holder

    async def aget(self) -> Dict[str, Any]:
        """Get the state of the actor. This method will get the state of the"""
        return await self.proxy_holder.aget_state(self.state_key, self.attribute)

    async def aset(self, value: Dict[str, Any]) -> None:
        """Set the state of the actor. This method will set the state of the"""
        return await self.proxy_holder.aset_state(self.state_key, self.attribute, value)


class StateProxy:
    """A class to proxy the state of an agent"""

    def __init__(self, proxy_holder: ProxyHolder, state_key: str) -> None:
        """Initialize the class with the proxy holder and the state key"""
        self.proxy_holder = proxy_holder
        self.state_key = state_key

    async def aget(self, attribute: str) -> Any:  # noqa: ANN401
        """Get the sstate attribute"""
        return await self.proxy_holder.aget_state(self.state_key, attribute)

    async def aset(self, attribute: str, value: Any) -> None:  # noqa: ANN401
        """Set the state of the actor. This method will set the state of the"""
        return await self.proxy_holder.aset_state(self.state_key, attribute, value)

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401
        """Get the state of the actor. This method will get the state of the"""
        if name in ["proxy_holder", "state_key", "aget", "aset"]:
            return super().__getattr__(name)  # type: ignore[return-value]
        # Check if runnning in async context
        try:
            asyncio.get_running_loop()
            return AGetProperty(self.proxy_holder, self.state_key, name)
        except RuntimeError:
            return unkoil(self.aget, name)

    def __setattr__(self, name: str, value: Any) -> None:  # noqa: ANN401
        """Set the state of the actor. This method will set the state of the"""
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
