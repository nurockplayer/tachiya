import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import get_settings


def test_settings_default_cors_allowed_origins(monkeypatch):
    monkeypatch.delenv("TACHIYA_CORS_ALLOWED_ORIGINS", raising=False)

    settings = get_settings()

    assert settings.cors_allowed_origins == (
        "http://localhost:3000",
        "http://localhost:3001",
    )


def test_settings_parses_cors_allowed_origins(monkeypatch):
    monkeypatch.setenv(
        "TACHIYA_CORS_ALLOWED_ORIGINS",
        " https://shop.example.com, http://localhost:3000 ,,",
    )

    settings = get_settings()

    assert settings.cors_allowed_origins == (
        "https://shop.example.com",
        "http://localhost:3000",
    )
