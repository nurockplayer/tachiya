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


def test_settings_default_voucher_code_prefix(monkeypatch):
    monkeypatch.delenv("TACHIYA_VOUCHER_CODE_PREFIX", raising=False)

    settings = get_settings()

    assert settings.voucher_code_prefix == "TACHIYA"


def test_settings_sanitizes_voucher_code_prefix(monkeypatch):
    monkeypatch.setenv("TACHIYA_VOUCHER_CODE_PREFIX", " tachiya live! 2026 ")

    settings = get_settings()

    assert settings.voucher_code_prefix == "TACHIYALIVE2026"


def test_settings_falls_back_for_blank_voucher_code_prefix(monkeypatch):
    monkeypatch.setenv("TACHIYA_VOUCHER_CODE_PREFIX", " !!! ")

    settings = get_settings()

    assert settings.voucher_code_prefix == "TACHIYA"
