from pydantic import BaseModel


class GymClassType(BaseModel):
    label: str
    value: int
    type: str


class GymClassTypesGroup(BaseModel):
    title: str
    options: list[GymClassType]


class Center(BaseModel):
    label: str
    value: int
    type: str


class CenterGroup(BaseModel):
    label: str
    weight: int
    options: list[Center]


class GymClass(BaseModel):
    date: str
    startTime: str
    endTime: str
    title: str
    activityId: int
    bookingId: str
    payment_type: str
    participationId: str | None
    instructor: str
    location: str
    centerName: str
    centerUrl: str
    duration: int
    activityUrl: str
    level: dict
    button: dict
