from pydantic.main import BaseModel


class SerializableObject(BaseModel):
    """SerializableObject is a simple object should be serializeable and deserailblie globalyy."""

    number: int

    @classmethod
    def get_identifier(cls):
        return "mock/serializable"

    async def ashrink(self):
        return self.number

    @classmethod
    async def aexpand(cls, value):
        return cls(number=value)


class GlobalObject(BaseModel):
    """GlobalObject is a simple object that can't be serialized and deserialized. It should get put on a shelve"""

    number: int


class SecondSerializableObject:
    """Another SerializableObject that has a id"""

    def __init__(self, id) -> None:
        self.id = id

    @classmethod
    def get_identifier(cls):
        return "mock/secondserializable"

    async def ashrink(self):
        return self.id

    @classmethod
    async def aexpand(cls, value):
        return cls(id=value)


class IdentifiableSerializableObject(BaseModel):
    """IdentifiableSerializableObject is a simple object that can be serialized and deserialized.
    it should get a global scope"""

    number: int

    @classmethod
    def get_identifier(cls) -> str:
        return "mock/identifiable"

    async def ashrink(self) -> str:
        return self.number

    @classmethod
    async def aexpand(cls, shrinked_value) -> "IdentifiableSerializableObject":
        return cls(number=shrinked_value)


class SecondObject:
    """Another SerializableObject that has a id"""

    pass

    def __init__(self, id) -> None:
        self.id = id

    @classmethod
    def get_identifier(cls):
        return "mock/secondobject"

    async def ashrink(self):
        return self.id

    @classmethod
    async def aexpand(cls, value):
        return cls(id=value)
