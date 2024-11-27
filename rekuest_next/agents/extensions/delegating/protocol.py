from typing import Any, Literal, Union
from pydantic import BaseModel, Field
from rekuest_next.api.schema import DefinitionInput
from uuid import uuid4


class InitMessage(BaseModel):
    type: Literal["INIT"]
    name: str


class RegisterMessage(BaseModel):
    type: Literal["REGISTER"]
    definition: DefinitionInput
    interface: str


class DoneRegistration(BaseModel):
    type: Literal["REGISTER_DONE"]


class DoneMessage(BaseModel):
    id: str
    type: Literal["DONE"]
    returns: dict[str, Any]


class ErrorMessage(BaseModel):
    id: str
    type: Literal["ERROR"]
    message: str


class StartRegistration(BaseModel):
    type: Literal["INIT_REGISTRATION"] = "INIT_REGISTRATION"


class AssignMessage(BaseModel):
    type: Literal["ASSIGN"] = "ASSIGN"
    interface: str
    id: str = Field(default_factory=lambda: str(uuid4()))
    kwargs: dict[str, Any]


InMessage = Union[
    RegisterMessage, DoneMessage, InitMessage, DoneRegistration, ErrorMessage
]

OutMessage = Union[StartRegistration, AssignMessage]


class In(BaseModel):
    message: InMessage = Field(discriminator="type")


class Out(BaseModel):
    message: OutMessage = Field(discriminator="type")
