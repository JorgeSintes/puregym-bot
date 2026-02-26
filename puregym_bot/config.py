from datetime import time
from enum import IntEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, SecretStr, ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


def valid_str(value: str) -> str:
    if value == "":
        raise ValidationError("Field not set")
    return value


def valid_secret(value: SecretStr) -> SecretStr:
    if value.get_secret_value() == "":
        raise ValidationError("Field not set")
    return value


def valid_list(value: list) -> list:
    if len(value) == 0:
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


class UserConfig(BaseModel):
    name: str
    telegram_id: int
    puregym_username: Annotated[str, AfterValidator(valid_str)]
    puregym_password: Annotated[SecretStr, AfterValidator(valid_secret)]


class Config(BaseSettings):
    telegram_token: Annotated[SecretStr, AfterValidator(valid_secret)] = SecretStr("")
    users: Annotated[list[UserConfig], AfterValidator(valid_list)] = Field(default_factory=list)
    logging_level: str = "INFO"

    max_days_in_advance: int = 28
    max_bookings: int = 18

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

    model_config = SettingsConfigDict(yaml_file="config.yaml", yaml_file_encoding="utf-8")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: BaseSettings,
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (YamlConfigSettingsSource(settings_cls),)  # type: ignore


config = Config()
