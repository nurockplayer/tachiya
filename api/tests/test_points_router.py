import asyncio
import sys
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.points_ledger import PointsLedger
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


def test_points_ledger_requires_internal_secret(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get("/points/ledger", params={"user_id": "user-1"})

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid internal secret"


def test_points_ledger_returns_recent_entries(monkeypatch):
    session = build_session()
    session.add_all(
        [
            PointsLedger(
                id="older-entry",
                user_id="user-1",
                amount=120,
                entry_type="credit",
                source_type="tachigo",
                reference_id="tachigo:redemption-1",
                created_at=datetime(2026, 1, 1, 0, 0, 0),
            ),
            PointsLedger(
                id="newer-entry",
                user_id="user-1",
                amount=-20,
                entry_type="debit",
                source_type="checkout",
                reference_id="checkout-1",
                expires_at=datetime(2026, 12, 31, 23, 59, 59),
                created_at=datetime(2026, 1, 2, 0, 0, 0),
            ),
        ],
    )
    session.commit()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/points/ledger",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"user_id": "user-1", "limit": 1},
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "user-1",
        "entries": [
            {
                "id": "newer-entry",
                "amount": -20,
                "entry_type": "debit",
                "source_type": "checkout",
                "reference_id": "checkout-1",
                "expires_at": "2026-12-31T23:59:59",
                "created_at": "2026-01-02T00:00:00",
            },
        ],
    }


def test_points_ledger_rejects_limit_above_max(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/points/ledger",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"user_id": "user-1", "limit": 101},
    )

    assert response.status_code == 422
