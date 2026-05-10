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
from models.identity_audit_event import IdentityAuditEvent
from models.identity_mapping import IdentityMapping
from routers import identity_mappings


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
    app.include_router(identity_mappings.router)

    def override_db():
        yield session

    app.dependency_overrides[identity_mappings.get_db] = override_db
    return TestClient(app)


def test_create_and_resolve_identity_mapping(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}

    create_response = client.post(
        "/identity-mappings",
        headers=headers,
        json={
            "saleor_customer_id": "saleor-user-1",
            "provider": "tachigo",
            "external_subject": "tachigo-user-1",
            "actor": "ops-user-1",
            "reason": "initial link",
        },
    )
    resolve_response = client.get(
        "/identity-mappings/resolve",
        headers=headers,
        params={"provider": "tachigo", "external_subject": "tachigo-user-1"},
    )

    assert create_response.status_code == 200
    assert create_response.json()["saleor_customer_id"] == "saleor-user-1"
    assert resolve_response.status_code == 200
    assert resolve_response.json() == {
        "saleor_customer_id": "saleor-user-1",
        "provider": "tachigo",
        "external_subject": "tachigo-user-1",
    }


def test_create_identity_mapping_rejects_blank_fields_before_writing(monkeypatch):
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    valid_payload = {
        "saleor_customer_id": "saleor-user-1",
        "provider": "tachigo",
        "external_subject": "tachigo-user-1",
        "actor": "ops-user-1",
        "reason": "initial link",
    }
    invalid_fields = {
        "saleor_customer_id": " ",
        "provider": " ",
        "external_subject": " ",
        "actor": " ",
    }

    for field, value in invalid_fields.items():
        session = build_session()
        client = build_client(session)
        payload = valid_payload | {field: value}

        response = client.post(
            "/identity-mappings",
            headers=headers,
            json=payload,
        )

        assert response.status_code == 422
        assert session.query(IdentityMapping).count() == 0
        assert session.query(IdentityAuditEvent).count() == 0


def test_list_identity_audit_events(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    client.post(
        "/identity-mappings",
        headers=headers,
        json={
            "saleor_customer_id": "saleor-user-1",
            "provider": "tachigo",
            "external_subject": "tachigo-user-1",
            "actor": "ops-user-1",
            "reason": "initial link",
        },
    )

    response = client.get("/identity-mappings/audit-events", headers=headers)

    assert response.status_code == 200
    event = response.json()["events"][0]
    assert event["created_at"] is not None
    assert event == {
        "action": "identity.linked",
        "actor": "ops-user-1",
        "source": "tachigo:tachigo-user-1",
        "target": "saleor:saleor-user-1",
        "reason": "initial link",
        "created_at": event["created_at"],
    }


def test_list_identity_audit_events_filters_fields_and_created_range(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    session.add_all(
        [
            IdentityAuditEvent(
                id="before-range",
                action="identity.linked",
                actor="ops-user-1",
                source="tachigo:tachigo-user-1",
                target="saleor:saleor-user-1",
                reason="before",
                created_at=datetime(2026, 1, 1, 23, 59, 59),
            ),
            IdentityAuditEvent(
                id="matching-old",
                action="identity.relinked",
                actor="ops-user-2",
                source="tachigo:tachigo-user-1",
                target="saleor:saleor-user-2",
                reason="older match",
                created_at=datetime(2026, 1, 2, 0, 0, 0),
            ),
            IdentityAuditEvent(
                id="matching-new",
                action="identity.relinked",
                actor="ops-user-2",
                source="tachigo:tachigo-user-1",
                target="saleor:saleor-user-2",
                reason="newer match",
                created_at=datetime(2026, 1, 3, 0, 0, 0),
            ),
            IdentityAuditEvent(
                id="after-range",
                action="identity.relinked",
                actor="ops-user-2",
                source="tachigo:tachigo-user-1",
                target="saleor:saleor-user-2",
                reason="after",
                created_at=datetime(2026, 1, 3, 0, 0, 1),
            ),
        ],
    )
    session.commit()

    response = client.get(
        "/identity-mappings/audit-events",
        headers=headers,
        params={
            "action": " identity.relinked ",
            "actor": " ops-user-2 ",
            "source": " tachigo:tachigo-user-1 ",
            "target": " saleor:saleor-user-2 ",
            "created_from": "2026-01-02T00:00:00",
            "created_to": "2026-01-03T00:00:00",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    assert [event["reason"] for event in response.json()["events"]] == [
        "newer match",
        "older match",
    ]


def test_list_identity_audit_events_rejects_invalid_created_range(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/identity-mappings/audit-events",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={
            "created_from": "2026-01-03T00:00:00",
            "created_to": "2026-01-02T00:00:00",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid created_at range"


def test_list_identity_audit_events_rejects_blank_filter(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/identity-mappings/audit-events",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"source": " "},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "source is required"


def test_list_identity_mappings(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    tachigo_response = client.post(
        "/identity-mappings",
        headers=headers,
        json={
            "saleor_customer_id": "saleor-user-1",
            "provider": "tachigo",
            "external_subject": "tachigo-user-1",
        },
    )
    twitch_response = client.post(
        "/identity-mappings",
        headers=headers,
        json={
            "saleor_customer_id": "saleor-user-2",
            "provider": "twitch",
            "external_subject": "twitch-user-1",
        },
    )
    client.delete(
        f"/identity-mappings/{tachigo_response.json()['id']}",
        headers=headers,
        params={"actor": "ops-user-1", "reason": "user requested unlink"},
    )

    active_response = client.get("/identity-mappings", headers=headers)
    tachigo_history_response = client.get(
        "/identity-mappings?provider=Tachigo&include_unlinked=true&limit=10",
        headers=headers,
    )

    assert tachigo_response.status_code == 200
    assert twitch_response.status_code == 200
    assert active_response.status_code == 200
    assert active_response.json()["mappings"] == [
        {
            "id": twitch_response.json()["id"],
            "saleor_customer_id": "saleor-user-2",
            "provider": "twitch",
            "external_subject": "twitch-user-1",
            "verified_at": twitch_response.json()["verified_at"],
            "unlinked_at": None,
        },
    ]
    assert tachigo_history_response.status_code == 200
    assert tachigo_history_response.json()["mappings"][0]["id"] == tachigo_response.json()["id"]
    assert tachigo_history_response.json()["mappings"][0]["unlinked_at"] is not None


def test_list_identity_mappings_rejects_invalid_query(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/identity-mappings?provider=%20",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "provider is required"


def test_resolve_identity_mapping_returns_404_for_missing_mapping(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/identity-mappings/resolve",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"provider": "tachigo", "external_subject": "unknown"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "identity mapping not found"


def test_unlink_identity_mapping(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    create_response = client.post(
        "/identity-mappings",
        headers=headers,
        json={
            "saleor_customer_id": "saleor-user-1",
            "provider": "tachigo",
            "external_subject": "tachigo-user-1",
        },
    )

    response = client.delete(
        f"/identity-mappings/{create_response.json()['id']}",
        headers=headers,
        params={"actor": "ops-user-1", "reason": "user requested unlink"},
    )

    assert response.status_code == 200
    assert response.json()["unlinked"] is True


def test_create_identity_mapping_relinks_unlinked_mapping(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    create_response = client.post(
        "/identity-mappings",
        headers=headers,
        json={
            "saleor_customer_id": "saleor-user-1",
            "provider": "tachigo",
            "external_subject": "tachigo-user-1",
        },
    )
    client.delete(
        f"/identity-mappings/{create_response.json()['id']}",
        headers=headers,
        params={"actor": "ops-user-1", "reason": "user requested unlink"},
    )

    relink_response = client.post(
        "/identity-mappings",
        headers=headers,
        json={
            "saleor_customer_id": "saleor-user-2",
            "provider": "Tachigo",
            "external_subject": "tachigo-user-1",
            "actor": "ops-user-2",
            "reason": "verified new owner",
        },
    )

    events_response = client.get("/identity-mappings/audit-events", headers=headers)
    assert relink_response.status_code == 200
    assert relink_response.json()["id"] == create_response.json()["id"]
    assert relink_response.json()["saleor_customer_id"] == "saleor-user-2"
    assert relink_response.json()["provider"] == "tachigo"
    assert relink_response.json()["unlinked_at"] is None
    event = events_response.json()["events"][0]
    assert event["created_at"] is not None
    assert event == {
        "action": "identity.relinked",
        "actor": "ops-user-2",
        "source": "tachigo:tachigo-user-1",
        "target": "saleor:saleor-user-2",
        "reason": "verified new owner",
        "created_at": event["created_at"],
    }


def test_identity_mapping_rejects_missing_internal_secret(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.post(
        "/identity-mappings",
        json={
            "saleor_customer_id": "saleor-user-1",
            "provider": "tachigo",
            "external_subject": "tachigo-user-1",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid internal secret"
