from functools import lru_cache
from typing import ClassVar, Final

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DEV_KEY: Final[str] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(env_file=".env")

    app_name: str = "MyGM API"
    allowed_origins: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("MYGM_ALLOWED_ORIGINS", "MYGM_API_CORS_ORIGINS"),
    )
    credential_key_id: str = Field(
        default="local-dev",
        validation_alias=AliasChoices("MYGM_CREDENTIAL_KEY_ID", "MYGM_API_CREDENTIAL_KEY_ID"),
    )
    credential_key: str = Field(
        default=DEFAULT_DEV_KEY,
        validation_alias="MYGM_CREDENTIAL_KEY_V1",
    )
    rate_limit_attempts: int = Field(
        default=20,
        validation_alias="MYGM_API_RATE_LIMIT_ATTEMPTS",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
