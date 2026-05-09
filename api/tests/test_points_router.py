import asyncio
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from routers import points
from services.points_service import PointsService


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
    app.include_router(points.router)

    def override_db():
        yield session

    app.dependency_overrides[points.get_db] = override_db
    return TestClient(app)


def test_points_balance_returns_current_balance(monkeypatch):
    session = build_session()
    asyncio.run(PointsService(session).credit("user-1", 120, "order-1"))
    asyncio.run(PointsService(session).debit("user-1", 20, "checkout-1"))
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/points/balance",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"user_id": "user-1"},
    )

    assert response.status_code == 200
    assert response.json() == {"user_id": "user-1", "balance": 100}


def test_points_balance_returns_zero_without_ledger_entries(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/points/balance",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"user_id": "new-user"},
    )

    assert response.status_code == 200
    assert response.json() == {"user_id": "new-user", "balance": 0}


def test_points_balance_rejects_missing_internal_secret(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get("/points/balance", params={"user_id": "user-1"})

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid internal secret"
