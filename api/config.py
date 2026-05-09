import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    tachigo_api_url: str = os.getenv("TACHIGO_API_URL", "http://localhost:8080")


def get_settings() -> Settings:
    return Settings(
        tachigo_api_url=os.getenv("TACHIGO_API_URL", "http://localhost:8080"),
    )
