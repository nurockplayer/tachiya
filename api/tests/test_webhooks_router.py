import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database
from database import Base
from main import app
from models.webhook_event import WebhookEvent


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
    def override_db():
        yield session

    app.dependency_overrides[database.get_db] = override_db
    return TestClient(app)


def test_list_webhook_events_filters_recent_events(monkeypatch):
    session = build_session()
    session.add_all(
        [
            WebhookEvent(
                event_id="evt-1",
                event_type="points.order_rewarded",
                occurred_at=datetime(2026, 1, 1, 0, 0, 0),
                received_at=datetime(2026, 1, 1, 0, 0, 1),
            ),
            WebhookEvent(
                event_id="evt-2",
                event_type="revenue_share.order_completed",
                occurred_at=datetime(2026, 1, 2, 0, 0, 0),
                received_at=datetime(2026, 1, 2, 0, 0, 1),
            ),
            WebhookEvent(
                event_id="evt-3",
                event_type="points.order_rewarded",
                occurred_at=datetime(2026, 1, 3, 0, 0, 0),
                received_at=datetime(2026, 1, 3, 0, 0, 1),
            ),
        ],
    )
    session.commit()
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    client = build_client(session)

    response = client.get(
        "/webhooks/events",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"event_type": " points.order_rewarded ", "limit": 10},
    )

    assert response.status_code == 200
    assert response.json() == {
        "events": [
            {
                "id": session.query(WebhookEvent)
                .filter(WebhookEvent.event_id == "evt-3")
                .one()
                .id,
                "event_id": "evt-3",
                "event_type": "points.order_rewarded",
                "occurred_at": "2026-01-03T00:00:00",
                "received_at": "2026-01-03T00:00:01",
            },
            {
                "id": session.query(WebhookEvent)
                .filter(WebhookEvent.event_id == "evt-1")
                .one()
                .id,
                "event_id": "evt-1",
                "event_type": "points.order_rewarded",
                "occurred_at": "2026-01-01T00:00:00",
                "received_at": "2026-01-01T00:00:01",
            },
        ],
    }


def test_list_webhook_events_filters_event_id_and_received_range(monkeypatch):
    session = build_session()
    session.add_all(
        [
            WebhookEvent(
                event_id="evt-before",
                event_type="points.order_rewarded",
                occurred_at=datetime(2026, 1, 1, 0, 0, 0),
                received_at=datetime(2026, 1, 1, 23, 59, 59),
            ),
            WebhookEvent(
                event_id="evt-target",
                event_type="points.order_rewarded",
                occurred_at=datetime(2026, 1, 2, 0, 0, 0),
                received_at=datetime(2026, 1, 2, 0, 0, 0),
            ),
            WebhookEvent(
                event_id="evt-after",
                event_type="points.order_rewarded",
                occurred_at=datetime(2026, 1, 3, 0, 0, 0),
                received_at=datetime(2026, 1, 3, 0, 0, 1),
            ),
        ],
    )
    session.commit()
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    client = build_client(session)

    response = client.get(
        "/webhooks/events",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={
            "event_id": " evt-target ",
            "received_from": "2026-01-02T00:00:00",
            "received_to": "2026-01-03T00:00:00",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    assert [event["event_id"] for event in response.json()["events"]] == ["evt-target"]


def test_list_webhook_events_requires_internal_secret(monkeypatch):
    session = build_session()
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    client = build_client(session)

    response = client.get("/webhooks/events")

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid internal secret"


def test_list_webhook_events_rejects_blank_event_type(monkeypatch):
    session = build_session()
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    client = build_client(session)

    response = client.get(
        "/webhooks/events",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"event_type": " "},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "event_type is required"


def test_list_webhook_events_rejects_blank_event_id(monkeypatch):
    session = build_session()
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    client = build_client(session)

    response = client.get(
        "/webhooks/events",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"event_id": " "},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "event_id is required"


def test_list_webhook_events_rejects_invalid_received_range(monkeypatch):
    session = build_session()
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    client = build_client(session)

    response = client.get(
        "/webhooks/events",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={
            "received_from": "2026-01-03T00:00:00",
            "received_to": "2026-01-02T00:00:00",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid received_at range"
