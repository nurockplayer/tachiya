from functools import lru_cache
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    tachiya_internal_shared_secret: str | None = Field(
        default=None,
        alias="TACHIYA_INTERNAL_SHARED_SECRET",
    )
    tachiya_voucher_prefix: str = Field(
        default="TY",
        alias="TACHIYA_VOUCHER_PREFIX",
    )
    tachiya_voucher_code_length: int = Field(
        default=10,
        alias="TACHIYA_VOUCHER_CODE_LENGTH",
    )
    tachigo_api_url: str = Field(
        default="http://localhost:8080",
        alias="TACHIGO_API_URL",
    )
    tachiya_redemptions_db_path: Path = Field(
        default=Path("data/redemptions.sqlite3"),
        alias="TACHIYA_REDEMPTIONS_DB_PATH",
    )

    @field_validator("tachiya_redemptions_db_path")
    @classmethod
    def resolve_redemptions_db_path(cls, value: Path) -> Path:
        if value.is_absolute():
            return value
        return BASE_DIR / value


@lru_cache
def get_settings() -> Settings:
    return Settings()
