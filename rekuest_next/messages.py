from typing import Any, List, Optional, TypeVar
from pydantic import BaseModel
from rekuest.api.schema import (
    LogLevelInput,
    ProvisionStatus,
    ReservationStatus,
    AssignationStatus,
)

T = TypeVar("T", bound=BaseModel)


class UpdatableModel(BaseModel):
    pass

    def update(self: T, use: BaseModel = None, in_place=True, **kwargs) -> Optional[T]:
        if in_place:
            if use:
                for key, value in use.dict().items():
                    if key in self.__fields__:
                        if value is not None:  # None is not a valid update!
                            setattr(self, key, value)
            if kwargs:
                for key in kwargs:
                    setattr(self, key, kwargs[key])

            return self
        else:
            copy = self.copy()
            copy.update(use=use, **kwargs)
            return copy


class Assignation(UpdatableModel):
    assignation: str
    reference: Optional[str]
    provision: Optional[str]
    reservation: Optional[str]
    args: Optional[List[Any]]
    returns: Optional[List[Any]]
    persist: Optional[bool]
    progress: Optional[int]
    log: Optional[bool]
    status: Optional[AssignationStatus]
    message: Optional[str]
    user: Optional[str]


class Unassignation(UpdatableModel):
    assignation: str
    provision: Optional[str]


class Provision(UpdatableModel):
    provision: str
    guardian: str
    template: Optional[str]
    status: Optional[ProvisionStatus]


class Inquiry(UpdatableModel):
    assignations: List[Assignation]


class Unprovision(UpdatableModel):
    provision: str
    message: Optional[str]


class Reservation(UpdatableModel):
    reference: Optional[str]
    reservation: str
    provision: Optional[str]
    template: Optional[str]
    node: Optional[str]
    status: Optional[ReservationStatus] = None
    message: Optional[str] = ""


class Unreservation(BaseModel):
    reservation: str


class AssignationLog(BaseModel):
    assignation: str
    level: LogLevelInput
    message: Optional[str]


class ProvisionLog(BaseModel):
    provision: str
    level: LogLevelInput
    message: Optional[str]
