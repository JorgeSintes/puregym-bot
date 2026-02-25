from typing import Annotated

from pydantic import AfterValidator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def valid_telegram_token(token: SecretStr) -> SecretStr:
    if token.get_secret_value() == "Empty":
        raise ValueError("TELEGRAM_TOKEN is not set")
    return token


class Config(BaseSettings):
    TELEGRAM_TOKEN: Annotated[SecretStr, AfterValidator(valid_telegram_token)] = (
        SecretStr("Empty")
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


config = Config()
