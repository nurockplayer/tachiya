import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main


def test_health_returns_liveness_status():
    assert main.health() == {"status": "ok"}


def test_app_uses_configured_cors_allowed_origins():
    cors_middleware = next(
        middleware
        for middleware in main.app.user_middleware
        if middleware.cls.__name__ == "CORSMiddleware"
    )

    assert cors_middleware.kwargs["allow_origins"] == (
        "http://localhost:3000",
        "http://localhost:3001",
    )


def test_cors_preflight_allows_configured_origin():
    client = TestClient(main.app)

    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_preflight_rejects_unconfigured_origin():
    client = TestClient(main.app)

    response = client.options(
        "/health",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_ready_returns_database_status(monkeypatch):
    monkeypatch.setattr(main, "check_database_ready", lambda: True)

    assert main.ready() == {"status": "ok", "checks": {"database": "ok"}}


def test_ready_returns_503_when_database_check_fails(monkeypatch):
    def fail_database_check():
        raise SQLAlchemyError("database unavailable")

    monkeypatch.setattr(main, "check_database_ready", fail_database_check)

    response = main.ready()

    assert response.status_code == 503
    assert response.body == b'{"status":"unavailable","checks":{"database":"error"}}'
