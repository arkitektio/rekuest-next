from pydantic.main import BaseModel


class SerializableObject(BaseModel):
    number: int

    async def ashrink(self):
        return self.number

    @classmethod
    async def aexpand(cls, value):
        return cls(number=value)


class GlobalObject(BaseModel):
    number: int


class SecondSerializableObject:
    def __init__(self, id) -> None:
        self.id = id


class IdentifiableSerializableObject(BaseModel):
    number: int

    @classmethod
    def get_identifier(cls):
        return "mock/identifiable"

    async def ashrink(self):
        return self.number

    @classmethod
    async def aexpand(cls, shrinked_value):
        return cls(number=shrinked_value)


class SecondObject:
    pass

    def __init__(self, id) -> None:
        self.id = id
