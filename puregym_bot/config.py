from datetime import time
from enum import IntEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


def valid_str(value: str) -> str:
    if value == "":
        raise ValidationError("Field not set")
    return value


def valid_secret(value: SecretStr) -> SecretStr:
    if value.get_secret_value() == "":
        raise ValidationError("Field not set")
    return value


class Weekday(IntEnum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


class TimeSlot(BaseModel):
    day_of_week: Weekday
    start_time: time
    end_time: time


class GymClassPreferences(BaseModel):
    interested_classes: list[int]
    interested_centers: list[int]
    available_time_slots: list[TimeSlot] = Field(default_factory=list)


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    TELEGRAM_TOKEN: Annotated[SecretStr, AfterValidator(valid_secret)] = SecretStr("")
    TELEGRAM_ID_WHITELIST: list[int] = []
    PUREGYM_USERNAME: Annotated[str, AfterValidator(valid_str)] = ""
    PUREGYM_PASSWORD: Annotated[SecretStr, AfterValidator(valid_secret)] = SecretStr("")

    MAX_DAYS_IN_ADVANCE: int = 28
    MAX_BOOKINGS: int = 18

    class_preferences: GymClassPreferences = GymClassPreferences(
        interested_classes=[
            34941,  # Bike power
            23742,  # Bike standard
        ],
        interested_centers=[
            123,  # Kbh Ø., Århusgade
            172,  # Kbh Ø., Strandvejen
        ],
        available_time_slots=[
            TimeSlot(
                day_of_week=Weekday.TUESDAY,
                start_time=time(hour=17, minute=0),
                end_time=time(hour=22, minute=0),
            ),
        ],
    )


config = Config()
