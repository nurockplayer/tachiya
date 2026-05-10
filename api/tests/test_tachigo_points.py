import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Settings
from database import Base
from routers import tachigo
from services.identity_mapping_service import IdentityMappingService
from services.tachigo import (
    TachigoIdentityPoints,
    TachigoPoints,
    TachigoUpstreamError,
    get_identity_points,
    get_user_points,
)


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
    assert (
        str(requests[0].url)
        == "http://tachigo.local/api/v1/internal/tachiya/users/points/balance?email=demo%40tachigo.io"
    )
    assert requests[0].headers["X-Tachiya-Internal-Secret"] == "shared-secret"


@pytest.mark.anyio
async def test_get_user_points_fails_closed_without_internal_secret(monkeypatch):
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
    monkeypatch.delenv("TACHIYA_INTERNAL_SHARED_SECRET", raising=False)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TachigoUpstreamError, match="tachigo internal secret is not configured"):
            await get_user_points("demo@tachigo.io", settings, client=client)

    assert requests == []


@pytest.mark.anyio
async def test_get_identity_points_calls_tachigo_identity_api(monkeypatch):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "provider": "tachigo",
                "external_subject": "tachigo-user-1",
                "spendable_balance": 123,
                "cumulative_total": 456,
            },
        )

    settings = Settings(tachigo_api_url="http://tachigo.local")
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await get_identity_points("tachigo", "tachigo-user-1", settings, client=client)

    assert result == TachigoIdentityPoints(
        provider="tachigo",
        external_subject="tachigo-user-1",
        spendable_balance=123,
        cumulative_total=456,
    )
    assert (
        str(requests[0].url)
        == "http://tachigo.local/internal/identity/tachigo/tachigo-user-1/points"
    )
    assert requests[0].headers["X-Tachiya-Internal-Secret"] == "shared-secret"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        {
            "provider": "wallet",
            "external_subject": "tachigo-user-1",
            "spendable_balance": 123,
            "cumulative_total": 456,
        },
        {
            "provider": "tachigo",
            "external_subject": "other-user",
            "spendable_balance": 123,
            "cumulative_total": 456,
        },
    ],
)
async def test_get_identity_points_rejects_upstream_identity_mismatch(monkeypatch, payload):
    settings = Settings(tachigo_api_url="http://tachigo.local")
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=payload)),
    ) as client:
        with pytest.raises(TachigoUpstreamError, match="tachigo upstream identity mismatch"):
            await get_identity_points("tachigo", "tachigo-user-1", settings, client=client)


@pytest.mark.anyio
async def test_get_identity_points_fails_closed_without_internal_secret(monkeypatch):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "provider": "tachigo",
                "external_subject": "tachigo-user-1",
                "spendable_balance": 123,
                "cumulative_total": 456,
            },
        )

    settings = Settings(tachigo_api_url="http://tachigo.local")
    monkeypatch.delenv("TACHIYA_INTERNAL_SHARED_SECRET", raising=False)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TachigoUpstreamError, match="tachigo internal secret is not configured"):
            await get_identity_points("tachigo", "tachigo-user-1", settings, client=client)

    assert requests == []


@pytest.mark.anyio
async def test_get_user_points_raises_for_upstream_error(monkeypatch):
    settings = Settings(tachigo_api_url="http://tachigo.local")
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(502, text="bad gateway")),
    ) as client:
        with pytest.raises(TachigoUpstreamError, match="tachigo upstream returned 502"):
            await get_user_points("demo@tachigo.io", settings, client=client)


@pytest.mark.anyio
async def test_get_user_points_raises_for_invalid_json_payload(monkeypatch):
    settings = Settings(tachigo_api_url="http://tachigo.local")
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, content=b"not-json"),
        ),
    ) as client:
        with pytest.raises(
            TachigoUpstreamError,
            match="tachigo upstream returned invalid points payload",
        ):
            await get_user_points("demo@tachigo.io", settings, client=client)


@pytest.mark.anyio
async def test_get_identity_points_raises_for_invalid_json_payload(monkeypatch):
    settings = Settings(tachigo_api_url="http://tachigo.local")
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, content=b"not-json"),
        ),
    ) as client:
        with pytest.raises(
            TachigoUpstreamError,
            match="tachigo upstream returned invalid points payload",
        ):
            await get_identity_points("tachigo", "tachigo-user-1", settings, client=client)


def build_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def build_client(session=None) -> TestClient:
    app = FastAPI()
    app.include_router(tachigo.router)
    if session is not None:

        def override_db():
            yield session

        app.dependency_overrides[tachigo.get_db] = override_db
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


def test_tachigo_identity_points_endpoint_returns_points(monkeypatch):
    session = build_session()
    IdentityMappingService(session).link_identity("saleor-user-1", "tachigo", "tachigo-user-1")
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    async def fake_get_identity_points(provider: str, external_subject: str, settings: Settings):
        assert provider == "tachigo"
        assert external_subject == "tachigo-user-1"
        assert settings.tachigo_api_url
        return TachigoIdentityPoints(
            provider=provider,
            external_subject=external_subject,
            spendable_balance=123,
            cumulative_total=456,
        )

    monkeypatch.setattr(tachigo, "get_identity_points", fake_get_identity_points)

    response = client.get(
        "/tachigo/identity/tachigo/tachigo-user-1/points",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "saleor_customer_id": "saleor-user-1",
        "provider": "tachigo",
        "external_subject": "tachigo-user-1",
        "spendable_balance": 123,
        "cumulative_total": 456,
    }


def test_tachigo_identity_points_query_endpoint_returns_points_for_special_subject(
    monkeypatch,
):
    session = build_session()
    IdentityMappingService(session).link_identity("saleor-user-1", "wallet", "eip155:1/0xabc")
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    async def fake_get_identity_points(provider: str, external_subject: str, settings: Settings):
        assert provider == "wallet"
        assert external_subject == "eip155:1/0xabc"
        assert settings.tachigo_api_url
        return TachigoIdentityPoints(
            provider=provider,
            external_subject=external_subject,
            spendable_balance=123,
            cumulative_total=456,
        )

    monkeypatch.setattr(tachigo, "get_identity_points", fake_get_identity_points)

    response = client.get(
        "/tachigo/identity/points",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"provider": " Wallet ", "external_subject": " eip155:1/0xabc "},
    )

    assert response.status_code == 200
    assert response.json() == {
        "saleor_customer_id": "saleor-user-1",
        "provider": "wallet",
        "external_subject": "eip155:1/0xabc",
        "spendable_balance": 123,
        "cumulative_total": 456,
    }


def test_tachigo_identity_points_endpoint_rejects_upstream_identity_mismatch(monkeypatch):
    session = build_session()
    IdentityMappingService(session).link_identity("saleor-user-1", "tachigo", "tachigo-user-1")
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    async def fake_get_identity_points(provider: str, external_subject: str, settings: Settings):
        return TachigoIdentityPoints(
            provider="wallet",
            external_subject=external_subject,
            spendable_balance=123,
            cumulative_total=456,
        )

    monkeypatch.setattr(tachigo, "get_identity_points", fake_get_identity_points)

    response = client.get(
        "/tachigo/identity/points",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"provider": "tachigo", "external_subject": "tachigo-user-1"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "tachigo upstream identity mismatch"


def test_tachigo_identity_points_query_endpoint_rejects_blank_filters(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    async def fail_get_identity_points(provider: str, external_subject: str, settings: Settings):
        raise AssertionError("upstream should not be called")

    monkeypatch.setattr(tachigo, "get_identity_points", fail_get_identity_points)

    response = client.get(
        "/tachigo/identity/points",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"provider": " ", "external_subject": "tachigo-user-1"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "provider is required"


def test_tachigo_identity_points_endpoint_returns_404_for_missing_mapping(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/tachigo/identity/tachigo/unknown/points",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "identity mapping not found"


def test_tachigo_identity_points_endpoint_maps_upstream_error(monkeypatch):
    session = build_session()
    IdentityMappingService(session).link_identity("saleor-user-1", "tachigo", "tachigo-user-1")
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    async def fake_get_identity_points(provider: str, external_subject: str, settings: Settings):
        raise TachigoUpstreamError("tachigo upstream returned 502")

    monkeypatch.setattr(tachigo, "get_identity_points", fake_get_identity_points)

    response = client.get(
        "/tachigo/identity/tachigo/tachigo-user-1/points",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "tachigo upstream returned 502"
