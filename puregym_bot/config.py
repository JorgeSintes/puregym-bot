from typing import Annotated

from pydantic import AfterValidator, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


def valid_str(value: str) -> str:
    if value == "":
        raise ValidationError("Field not set")
    return value


def valid_secret(value: SecretStr) -> SecretStr:
    if value.get_secret_value() == "":
        raise ValidationError("Field not set")
    return value


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    TELEGRAM_TOKEN: Annotated[SecretStr, AfterValidator(valid_secret)] = SecretStr("")
    TELEGRAM_ID_WHITELIST: list[int] = []
    PUREGYM_USERNAME: Annotated[str, AfterValidator(valid_str)] = ""
    PUREGYM_PASSWORD: Annotated[SecretStr, AfterValidator(valid_secret)] = SecretStr("")

    INTERESTED_CLASSES: list[str] = ["Bike Power", "Bike Standard"]
    INTERESTED_CENTERS: list[str] = ["Kbh Ø., Århusgade", "Kbh Ø., Strandvejen"]
    MAX_DAYS_IN_ADVANCE: int = 28
    MAX_BOOKINGS: int = 18


config = Config()
