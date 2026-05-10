import os
from dataclasses import dataclass

DEFAULT_CORS_ALLOWED_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:3001",
)
DEFAULT_VOUCHER_CODE_PREFIX = "TACHIYA"


@dataclass(frozen=True)
class Settings:
    tachigo_api_url: str = os.getenv("TACHIGO_API_URL", "http://localhost:8080")
    cors_allowed_origins: tuple[str, ...] = DEFAULT_CORS_ALLOWED_ORIGINS
    voucher_code_prefix: str = DEFAULT_VOUCHER_CODE_PREFIX


def get_settings() -> Settings:
    return Settings(
        tachigo_api_url=os.getenv("TACHIGO_API_URL", "http://localhost:8080"),
        cors_allowed_origins=parse_cors_allowed_origins(
            os.getenv("TACHIYA_CORS_ALLOWED_ORIGINS"),
        ),
        voucher_code_prefix=parse_voucher_code_prefix(
            os.getenv("TACHIYA_VOUCHER_CODE_PREFIX"),
        ),
    )


def parse_cors_allowed_origins(raw_value: str | None) -> tuple[str, ...]:
    if not raw_value:
        return DEFAULT_CORS_ALLOWED_ORIGINS

    origins = tuple(origin.strip() for origin in raw_value.split(",") if origin.strip())
    return origins or DEFAULT_CORS_ALLOWED_ORIGINS


def parse_voucher_code_prefix(raw_value: str | None) -> str:
    if not raw_value:
        return DEFAULT_VOUCHER_CODE_PREFIX

    prefix = "".join(
        character
        for character in raw_value.strip().upper()
        if character.isalnum() or character == "-"
    ).strip("-")
    return prefix or DEFAULT_VOUCHER_CODE_PREFIX


def is_internal_shared_secret_configured() -> bool:
    return bool(os.getenv("TACHIYA_INTERNAL_SHARED_SECRET", "").strip())
