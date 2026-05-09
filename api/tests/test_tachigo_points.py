import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Settings
from routers import tachigo
from services.tachigo import TachigoPoints, TachigoUpstreamError, get_user_points


@pytest.mark.anyio
async def test_get_user_points_calls_tachigo_internal_api(monkeypatch):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "email": "demo@tachigo.io",
                "spendable_balance": 123,
                "cumulative_total": 456,
            },
        )

    settings = Settings(tachigo_api_url="http://tachigo.local")
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await get_user_points("demo@tachigo.io", settings, client=client)

    assert result == TachigoPoints(
        email="demo@tachigo.io",
        spendable_balance=123,
        cumulative_total=456,
    )
    assert str(requests[0].url) == "http://tachigo.local/internal/users/points?email=demo%40tachigo.io"
    assert requests[0].headers["X-Tachiya-Internal-Secret"] == "shared-secret"


@pytest.mark.anyio
async def test_get_user_points_raises_for_upstream_error(monkeypatch):
    settings = Settings(tachigo_api_url="http://tachigo.local")
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(502, text="bad gateway")),
    ) as client:
        with pytest.raises(TachigoUpstreamError, match="tachigo upstream returned 502"):
            await get_user_points("demo@tachigo.io", settings, client=client)


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(tachigo.router)
    return TestClient(app)


def test_tachigo_points_endpoint_returns_points(monkeypatch):
    client = build_client()
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    async def fake_get_user_points(email: str, settings: Settings):
        assert email == "demo@tachigo.io"
        assert settings.tachigo_api_url
        return TachigoPoints(email=email, spendable_balance=123, cumulative_total=456)

    monkeypatch.setattr(tachigo, "get_user_points", fake_get_user_points)

    response = client.get(
        "/tachigo/users/points",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"email": "demo@tachigo.io"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "email": "demo@tachigo.io",
        "spendable_balance": 123,
        "cumulative_total": 456,
    }


def test_tachigo_points_endpoint_rejects_missing_secret(monkeypatch):
    client = build_client()
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get("/tachigo/users/points", params={"email": "demo@tachigo.io"})

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid internal secret"


def test_tachigo_points_endpoint_maps_upstream_error(monkeypatch):
    client = build_client()
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    async def fake_get_user_points(email: str, settings: Settings):
        raise TachigoUpstreamError("tachigo upstream returned 502")

    monkeypatch.setattr(tachigo, "get_user_points", fake_get_user_points)

    response = client.get(
        "/tachigo/users/points",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"email": "demo@tachigo.io"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "tachigo upstream returned 502"
