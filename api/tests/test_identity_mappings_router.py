import sys
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
    assert response.json()["events"][0] == {
        "action": "identity.linked",
        "actor": "ops-user-1",
        "source": "tachigo:tachigo-user-1",
        "target": "saleor:saleor-user-1",
        "reason": "initial link",
    }


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
