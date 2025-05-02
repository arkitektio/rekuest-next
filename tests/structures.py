"""This file contains the structures used in the tests."""

from pydantic.main import BaseModel


class SerializableObject(BaseModel):
    """SerializableObject is a simple object should be serializeable and deserailblie globalyy."""

    number: int

    @classmethod
    def get_identifier(cls) -> str:
        """Get the identifier of the object."""
        return "mock/serializable"

    async def ashrink(self) -> str:
        """Shrink the object to its id."""
        return self.number

    @classmethod
    async def aexpand(cls, value: str) -> "SerializableObject":
        """Expand the object from its id."""
        return cls(number=value)


class GlobalObject(BaseModel):
    """GlobalObject is a simple object that can't be serialized and deserialized. It should get put on a shelve"""

    number: int


class SecondSerializableObject:
    """Another SerializableObject that has a id"""

    def __init__(self, id: str) -> None:
        """Initialize the object with an id."""
        self.id = id

    @classmethod
    def get_identifier(cls) -> str:
        """Get the identifier of the object."""
        return "mock/secondserializable"

    async def ashrink(self) -> str:
        """Shrink the object to its id."""
        return self.id

    @classmethod
    async def aexpand(cls, value: str) -> "SecondSerializableObject":
        """Expand the object from its id."""
        return cls(id=value)


class IdentifiableSerializableObject(BaseModel):
    """IdentifiableSerializableObject is a simple object that can be serialized and deserialized.
    it should get a global scope"""

    number: int

    @classmethod
    def get_identifier(cls) -> str:
        """Get the identifier of the object."""
        return "mock/identifiable"

    async def ashrink(self) -> str:
        """Shrink the object to its id."""
        return self.number

    @classmethod
    async def aexpand(cls, shrinked_value: str) -> "IdentifiableSerializableObject":
        """Expand the object from its id."""
        return cls(number=shrinked_value)


class SecondObject:
    """Another SerializableObject that has a id"""

    pass

    def __init__(self, id: str) -> None:  # noqa: D107
        """Initialize the object with an id.

        Args:
            id (str): The id of the object.
        """
        self.id = id

    @classmethod
    def get_identifier(cls) -> str:
        """Get the identifier of the object."""
        return "mock/secondobject"

    async def ashrink(self) -> str:
        """Shrink the object to its id."""
        return self.id

    @classmethod
    async def aexpand(cls, value: str) -> "SecondObject":
        """Expand the object from its id."""
        return cls(id=value)
