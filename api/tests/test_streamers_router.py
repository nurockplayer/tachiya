import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from routers import streamers


def build_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def build_client(session) -> TestClient:
    app = FastAPI()
    app.include_router(streamers.router)

    def override_db():
        yield session

    app.dependency_overrides[streamers.get_db] = override_db
    return TestClient(app)


def test_create_and_get_streamer_profile(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}

    create_response = client.post(
        "/streamers",
        headers=headers,
        json={
            "slug": " Streamer-One ",
            "display_name": " Streamer One ",
            "saleor_collection_id": " collection-1 ",
            "commission_bps": 1250,
        },
    )
    get_response = client.get("/streamers/Streamer-One", headers=headers)

    assert create_response.status_code == 200
    assert create_response.json()["slug"] == "streamer-one"
    assert create_response.json()["display_name"] == "Streamer One"
    assert create_response.json()["saleor_collection_id"] == "collection-1"
    assert create_response.json()["commission_bps"] == 1250
    assert create_response.json()["active"] is True
    assert get_response.status_code == 200
    assert get_response.json()["id"] == create_response.json()["id"]


def test_create_streamer_profile_rejects_missing_internal_secret(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.post(
        "/streamers",
        json={"slug": "streamer-one", "display_name": "Streamer One"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid internal secret"


def test_create_streamer_profile_rejects_invalid_payload(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.post(
        "/streamers",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={"slug": " ", "display_name": "Streamer One", "commission_bps": 10001},
    )

    assert response.status_code == 422


def test_create_streamer_profile_rejects_duplicate_slug(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    payload = {"slug": "streamer-one", "display_name": "Streamer One"}
    first_response = client.post("/streamers", headers=headers, json=payload)
    second_response = client.post(
        "/streamers",
        headers=headers,
        json=payload | {"display_name": "Streamer Duplicate"},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "streamer profile already exists"


def test_get_streamer_profile_returns_404(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/streamers/missing-streamer",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "streamer profile not found"
