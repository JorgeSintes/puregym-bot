from datetime import time
from enum import IntEnum
from functools import lru_cache
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, SecretStr, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


def valid_str(value: str) -> str:
    if value == "":
        raise ValueError("Field not set")
    return value


def valid_secret(value: SecretStr) -> SecretStr:
    if value.get_secret_value() == "":
        raise ValueError("Field not set")
    return value


def valid_list(value: list) -> list:
    if len(value) == 0:
        raise ValueError("Field not set")
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

    @model_validator(mode="after")
    def validate_non_overlapping_time_slots(self):
        slots_by_day: dict[Weekday, list[TimeSlot]] = {}
        for slot in self.available_time_slots:
            slots_by_day.setdefault(slot.day_of_week, []).append(slot)

        for day, slots in slots_by_day.items():
            sorted_slots = sorted(slots, key=lambda slot: (slot.start_time, slot.end_time))
            for previous, current in zip(sorted_slots, sorted_slots[1:]):
                if current.start_time < previous.end_time:
                    raise ValueError(
                        "Overlapping time slots are not allowed for "
                        f"{Weekday(day).name}: {previous.start_time.isoformat()}-{previous.end_time.isoformat()} "
                        f"overlaps with {current.start_time.isoformat()}-{current.end_time.isoformat()}"
                    )

        return self


class Config(BaseSettings):
    telegram_token: Annotated[SecretStr, AfterValidator(valid_secret)] = SecretStr("")
    name: str
    telegram_id: int
    puregym_username: Annotated[str, AfterValidator(valid_str)]
    puregym_password: Annotated[SecretStr, AfterValidator(valid_secret)]
    class_preferences: GymClassPreferences
    logging_level: str = "INFO"

    max_days_in_advance: int = 28
    max_bookings: int = 18
    booking_reminder_hours: int = 24
    pending_auto_cancel_hours: int = 3
    booking_interval_seconds: int = 60

    model_config = SettingsConfigDict(yaml_file="config.yaml", yaml_file_encoding="utf-8")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (YamlConfigSettingsSource(settings_cls),)  # type: ignore


@lru_cache(maxsize=1)
def get_config() -> Config:
    return Config()  # type: ignore[call-arg]


def clear_config_cache() -> None:
    get_config.cache_clear()
