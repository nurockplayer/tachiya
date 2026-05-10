import hashlib
import hmac
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.streamer import StreamerProductAssignment, StreamerProfile, StreamerRevenueShareRecord
from models.webhook_event import WebhookEvent
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


def build_client(session, *, raise_server_exceptions: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(streamers.router)

    def override_db():
        yield session

    app.dependency_overrides[streamers.get_db] = override_db
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


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


def test_streamer_profile_path_endpoints_reject_blank_slug(monkeypatch):
    session = build_session()
    client = build_client(session, raise_server_exceptions=False)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}

    get_response = client.get("/streamers/%20", headers=headers)
    patch_response = client.patch(
        "/streamers/%20",
        headers=headers,
        json={"display_name": "Renamed"},
    )
    catalog_response = client.get("/streamers/%20/catalog", headers=headers)

    assert get_response.status_code == 422
    assert get_response.json()["detail"] == "slug is required"
    assert patch_response.status_code == 422
    assert patch_response.json()["detail"] == "slug is required"
    assert catalog_response.status_code == 422
    assert catalog_response.json()["detail"] == "slug is required"


def test_update_streamer_profile(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    create_response = client.post(
        "/streamers",
        headers=headers,
        json={"slug": "streamer-one", "display_name": "One", "saleor_collection_id": "collection-1"},
    )

    response = client.patch(
        "/streamers/Streamer-One",
        headers=headers,
        json={
            "display_name": " Streamer Uno ",
            "saleor_collection_id": " ",
            "commission_bps": 1250,
            "active": False,
        },
    )

    assert create_response.status_code == 200
    assert response.status_code == 200
    assert response.json()["id"] == create_response.json()["id"]
    assert response.json()["slug"] == "streamer-one"
    assert response.json()["display_name"] == "Streamer Uno"
    assert response.json()["saleor_collection_id"] is None
    assert response.json()["commission_bps"] == 1250
    assert response.json()["active"] is False


def test_update_streamer_profile_rejects_empty_payload(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.patch(
        "/streamers/streamer-one",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "at least one field is required"


def test_update_streamer_profile_returns_404(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.patch(
        "/streamers/missing-streamer",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={"display_name": "Missing"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "streamer profile not found"


def test_list_streamer_profiles(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    client.post(
        "/streamers",
        headers=headers,
        json={"slug": "zeta", "display_name": "Zeta", "saleor_collection_id": "collection-z"},
    )
    client.post(
        "/streamers",
        headers=headers,
        json={"slug": "alpha", "display_name": "Alpha", "saleor_collection_id": "collection-a"},
    )
    client.post(
        "/streamers",
        headers=headers,
        json={"slug": "inactive", "display_name": "Inactive", "active": False},
    )

    response = client.get("/streamers?limit=10", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "streamers": [
            {
                "slug": "alpha",
                "display_name": "Alpha",
                "saleor_collection_id": "collection-a",
            },
            {
                "slug": "zeta",
                "display_name": "Zeta",
                "saleor_collection_id": "collection-z",
            },
        ],
    }


def test_list_streamer_profiles_rejects_invalid_limit(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/streamers?limit=101",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
    )

    assert response.status_code == 422


def test_list_streamer_profiles_for_admin(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    active_response = client.post(
        "/streamers",
        headers=headers,
        json={
            "slug": "streamer-one",
            "display_name": "Streamer One",
            "saleor_collection_id": "collection-1",
            "commission_bps": 1000,
        },
    )
    inactive_response = client.post(
        "/streamers",
        headers=headers,
        json={
            "slug": "inactive-streamer",
            "display_name": "Inactive Streamer",
            "commission_bps": 1250,
            "active": False,
        },
    )

    response = client.get("/streamers/profiles?active=false&limit=10", headers=headers)
    discovery_response = client.get("/streamers?limit=10", headers=headers)

    assert active_response.status_code == 200
    assert inactive_response.status_code == 200
    assert response.status_code == 200
    assert response.json() == {
        "profiles": [
            {
                "id": inactive_response.json()["id"],
                "slug": "inactive-streamer",
                "display_name": "Inactive Streamer",
                "saleor_collection_id": None,
                "commission_bps": 1250,
                "active": False,
                "created_at": inactive_response.json()["created_at"],
                "updated_at": inactive_response.json()["updated_at"],
            },
        ],
    }
    assert discovery_response.status_code == 200
    assert discovery_response.json()["streamers"] == [
        {
            "slug": "streamer-one",
            "display_name": "Streamer One",
            "saleor_collection_id": "collection-1",
        },
    ]


def test_list_streamer_profiles_for_admin_filters_slug_and_created_range(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    for slug, display_name in [
        ("streamer-before", "Before"),
        ("streamer-one", "One"),
        ("streamer-after", "After"),
    ]:
        client.post("/streamers", headers=headers, json={"slug": slug, "display_name": display_name})
    profiles = {profile.slug: profile for profile in session.query(StreamerProfile).all()}
    profiles["streamer-before"].created_at = datetime(2026, 1, 1, 23, 59, 59)
    profiles["streamer-one"].created_at = datetime(2026, 1, 2, 12, 0, 0)
    profiles["streamer-after"].created_at = datetime(2026, 1, 3, 0, 0, 1)
    session.commit()

    response = client.get(
        "/streamers/profiles",
        headers=headers,
        params={
            "slug": " Streamer-One ",
            "created_from": "2026-01-02T00:00:00",
            "created_to": "2026-01-03T00:00:00",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    assert [profile["slug"] for profile in response.json()["profiles"]] == ["streamer-one"]


def test_list_streamer_profiles_for_admin_rejects_invalid_filters(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}

    blank_slug_response = client.get("/streamers/profiles?slug=%20", headers=headers)
    invalid_range_response = client.get(
        "/streamers/profiles",
        headers=headers,
        params={
            "created_from": "2026-01-03T00:00:00",
            "created_to": "2026-01-02T00:00:00",
        },
    )

    assert blank_slug_response.status_code == 422
    assert blank_slug_response.json()["detail"] == "slug is required"
    assert invalid_range_response.status_code == 422
    assert invalid_range_response.json()["detail"] == "invalid created_at range"


def test_create_and_get_streamer_product_assignment(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    streamer_response = client.post(
        "/streamers",
        headers=headers,
        json={"slug": "streamer-one", "display_name": "Streamer One"},
    )

    assign_response = client.post(
        "/streamers/product-assignments",
        headers=headers,
        json={
            "saleor_product_id": " product-1 ",
            "streamer_slug": " Streamer-One ",
            "source": " saleor-metadata ",
        },
    )
    get_response = client.get("/streamers/product-assignments/product-1", headers=headers)

    assert streamer_response.status_code == 200
    assert assign_response.status_code == 200
    assert assign_response.json()["saleor_product_id"] == "product-1"
    assert assign_response.json()["streamer_profile_id"] == streamer_response.json()["id"]
    assert assign_response.json()["streamer_slug"] == "streamer-one"
    assert assign_response.json()["source"] == "saleor-metadata"
    assert get_response.status_code == 200
    assert get_response.json()["id"] == assign_response.json()["id"]


def test_streamer_product_assignment_updates_existing_product(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    client.post("/streamers", headers=headers, json={"slug": "streamer-one", "display_name": "One"})
    second_streamer_response = client.post(
        "/streamers",
        headers=headers,
        json={"slug": "streamer-two", "display_name": "Two"},
    )
    first_assignment_response = client.post(
        "/streamers/product-assignments",
        headers=headers,
        json={"saleor_product_id": "product-1", "streamer_slug": "streamer-one"},
    )

    updated_assignment_response = client.post(
        "/streamers/product-assignments",
        headers=headers,
        json={
            "saleor_product_id": "product-1",
            "streamer_slug": "streamer-two",
            "source": "manual-correction",
        },
    )

    assert first_assignment_response.status_code == 200
    assert updated_assignment_response.status_code == 200
    assert updated_assignment_response.json()["id"] == first_assignment_response.json()["id"]
    assert updated_assignment_response.json()["streamer_profile_id"] == second_streamer_response.json()["id"]
    assert updated_assignment_response.json()["streamer_slug"] == "streamer-two"
    assert updated_assignment_response.json()["source"] == "manual-correction"


def test_streamer_product_assignment_rejects_missing_streamer(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.post(
        "/streamers/product-assignments",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={"saleor_product_id": "product-1", "streamer_slug": "missing-streamer"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "streamer profile not found"


def test_list_streamer_product_assignments(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    client.post("/streamers", headers=headers, json={"slug": "streamer-one", "display_name": "One"})
    client.post("/streamers", headers=headers, json={"slug": "streamer-two", "display_name": "Two"})
    first_assignment_response = client.post(
        "/streamers/product-assignments",
        headers=headers,
        json={
            "saleor_product_id": "product-1",
            "streamer_slug": "streamer-one",
            "source": "saleor-metadata",
        },
    )
    client.post(
        "/streamers/product-assignments",
        headers=headers,
        json={
            "saleor_product_id": "product-2",
            "streamer_slug": "streamer-two",
            "source": "saleor-metadata",
        },
    )

    response = client.get(
        "/streamers/product-assignments?streamer_slug=Streamer-One&source=saleor-metadata&limit=10",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "assignments": [
            {
                "id": first_assignment_response.json()["id"],
                "saleor_product_id": "product-1",
                "streamer_profile_id": first_assignment_response.json()["streamer_profile_id"],
                "streamer_slug": "streamer-one",
                "source": "saleor-metadata",
                "created_at": first_assignment_response.json()["created_at"],
                "updated_at": first_assignment_response.json()["updated_at"],
            },
        ],
    }


def test_list_streamer_product_assignments_filters_created_range(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    client.post("/streamers", headers=headers, json={"slug": "streamer-one", "display_name": "One"})
    for product_id in ["product-before", "product-start", "product-end", "product-after"]:
        client.post(
            "/streamers/product-assignments",
            headers=headers,
            json={
                "saleor_product_id": product_id,
                "streamer_slug": "streamer-one",
                "source": "saleor-metadata",
            },
        )

    assignments = {
        assignment.saleor_product_id: assignment
        for assignment in session.query(StreamerProductAssignment).all()
    }
    assignments["product-before"].created_at = datetime(2026, 1, 1, 23, 59, 59)
    assignments["product-start"].created_at = datetime(2026, 1, 2, 0, 0, 0)
    assignments["product-end"].created_at = datetime(2026, 1, 3, 0, 0, 0)
    assignments["product-after"].created_at = datetime(2026, 1, 3, 0, 0, 1)
    session.commit()

    response = client.get(
        "/streamers/product-assignments",
        headers=headers,
        params={
            "created_from": "2026-01-02T00:00:00",
            "created_to": "2026-01-03T00:00:00",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    assert [assignment["saleor_product_id"] for assignment in response.json()["assignments"]] == [
        "product-end",
        "product-start",
    ]


def test_list_streamer_product_assignments_rejects_invalid_query(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/streamers/product-assignments?source=%20",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "source is required"


def test_list_streamer_product_assignments_rejects_invalid_created_range(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/streamers/product-assignments",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={
            "created_from": "2026-01-03T00:00:00",
            "created_to": "2026-01-02T00:00:00",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid created_at range"


def test_get_streamer_product_assignment_returns_404(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/streamers/product-assignments/missing-product",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "streamer product assignment not found"


def test_delete_streamer_product_assignment(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    client.post("/streamers", headers=headers, json={"slug": "streamer-one", "display_name": "One"})
    assign_response = client.post(
        "/streamers/product-assignments",
        headers=headers,
        json={"saleor_product_id": "product-1", "streamer_slug": "streamer-one"},
    )

    delete_response = client.delete("/streamers/product-assignments/product-1", headers=headers)
    get_response = client.get("/streamers/product-assignments/product-1", headers=headers)
    preview_response = client.post(
        "/streamers/revenue-shares/preview",
        headers=headers,
        json={
            "order_id": "order-1",
            "lines": [{"saleor_product_id": "product-1", "gross_amount": 1200}],
        },
    )

    assert assign_response.status_code == 200
    assert delete_response.status_code == 200
    assert delete_response.json()["id"] == assign_response.json()["id"]
    assert delete_response.json()["saleor_product_id"] == "product-1"
    assert get_response.status_code == 404
    assert preview_response.json()["unassigned_product_ids"] == ["product-1"]


def test_delete_streamer_product_assignment_returns_404(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.delete(
        "/streamers/product-assignments/missing-product",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "streamer product assignment not found"


def test_streamer_product_assignment_path_endpoints_reject_blank_product_id(monkeypatch):
    session = build_session()
    client = build_client(session, raise_server_exceptions=False)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    client.post("/streamers", headers=headers, json={"slug": "streamer-one", "display_name": "One"})
    client.post(
        "/streamers/product-assignments",
        headers=headers,
        json={"saleor_product_id": "product-1", "streamer_slug": "streamer-one"},
    )

    get_response = client.get("/streamers/product-assignments/%20", headers=headers)
    delete_response = client.delete("/streamers/product-assignments/%20", headers=headers)

    assert get_response.status_code == 422
    assert get_response.json()["detail"] == "saleor_product_id is required"
    assert delete_response.status_code == 422
    assert delete_response.json()["detail"] == "saleor_product_id is required"
    assert session.query(StreamerProductAssignment).count() == 1


def test_get_streamer_catalog(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    client.post(
        "/streamers",
        headers=headers,
        json={
            "slug": " Streamer-One ",
            "display_name": " Streamer One ",
            "saleor_collection_id": " collection-1 ",
        },
    )
    client.post(
        "/streamers",
        headers=headers,
        json={"slug": "streamer-two", "display_name": "Streamer Two"},
    )
    client.post(
        "/streamers/product-assignments",
        headers=headers,
        json={"saleor_product_id": "product-2", "streamer_slug": "streamer-one"},
    )
    client.post(
        "/streamers/product-assignments",
        headers=headers,
        json={"saleor_product_id": "product-1", "streamer_slug": "streamer-one"},
    )
    client.post(
        "/streamers/product-assignments",
        headers=headers,
        json={"saleor_product_id": "other-product", "streamer_slug": "streamer-two"},
    )

    response = client.get("/streamers/Streamer-One/catalog", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "streamer": {
            "slug": "streamer-one",
            "display_name": "Streamer One",
            "saleor_collection_id": "collection-1",
        },
        "saleor_product_ids": ["product-2", "product-1"],
    }


def test_get_streamer_catalog_returns_404_for_inactive_profile(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    client.post(
        "/streamers",
        headers=headers,
        json={"slug": "streamer-one", "display_name": "Streamer One", "active": False},
    )

    response = client.get("/streamers/streamer-one/catalog", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "streamer catalog not found"


def test_preview_streamer_revenue_shares(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    client.post(
        "/streamers",
        headers=headers,
        json={"slug": "streamer-one", "display_name": "One", "commission_bps": 1250},
    )
    client.post(
        "/streamers/product-assignments",
        headers=headers,
        json={"saleor_product_id": "product-1", "streamer_slug": "streamer-one"},
    )

    response = client.post(
        "/streamers/revenue-shares/preview",
        headers=headers,
        json={
            "order_id": " saleor-order-1 ",
            "lines": [
                {"saleor_product_id": " product-1 ", "gross_amount": 1200},
                {"saleor_product_id": "missing-product", "gross_amount": 300},
                {"saleor_product_id": "missing-product", "gross_amount": 100},
            ],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "order_id": "saleor-order-1",
        "shares": [
            {
                "streamer_slug": "streamer-one",
                "gross_amount": 1200,
                "commission_bps": 1250,
                "share_amount": 150,
            },
        ],
        "unassigned_product_ids": ["missing-product"],
    }


def test_preview_streamer_revenue_shares_rejects_invalid_payload(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.post(
        "/streamers/revenue-shares/preview",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={
            "order_id": "order-1",
            "lines": [{"saleor_product_id": "product-1", "gross_amount": 0}],
        },
    )

    assert response.status_code == 422


def test_revenue_share_endpoints_reject_non_strict_gross_amount(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}

    for endpoint in ["/streamers/revenue-shares/preview", "/streamers/revenue-shares/record"]:
        for gross_amount in [True, "1200"]:
            response = client.post(
                endpoint,
                headers=headers,
                json={
                    "order_id": "order-1",
                    "lines": [{"saleor_product_id": "product-1", "gross_amount": gross_amount}],
                },
            )

            assert response.status_code == 422


def test_record_streamer_revenue_shares(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    streamer_response = client.post(
        "/streamers",
        headers=headers,
        json={"slug": "streamer-one", "display_name": "One", "commission_bps": 1250},
    )
    client.post(
        "/streamers/product-assignments",
        headers=headers,
        json={"saleor_product_id": "product-1", "streamer_slug": "streamer-one"},
    )

    response = client.post(
        "/streamers/revenue-shares/record",
        headers=headers,
        json={
            "order_id": "saleor-order-1",
            "lines": [
                {"saleor_product_id": "product-1", "gross_amount": 1200},
                {"saleor_product_id": "missing-product", "gross_amount": 300},
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["order_id"] == "saleor-order-1"
    assert response.json()["unassigned_product_ids"] == ["missing-product"]
    assert response.json()["records"][0]["streamer_profile_id"] == streamer_response.json()["id"]
    assert response.json()["records"][0]["streamer_slug"] == "streamer-one"
    assert response.json()["records"][0]["gross_amount"] == 1200
    assert response.json()["records"][0]["commission_bps"] == 1250
    assert response.json()["records"][0]["share_amount"] == 150
    assert response.json()["records"][0]["status"] == "pending"
    assert response.json()["records"][0]["created_at"]
    assert response.json()["records"][0]["updated_at"]


def test_record_streamer_revenue_shares_rejects_conflicting_replay(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    client.post(
        "/streamers",
        headers=headers,
        json={"slug": "streamer-one", "display_name": "One", "commission_bps": 1250},
    )
    client.post(
        "/streamers/product-assignments",
        headers=headers,
        json={"saleor_product_id": "product-1", "streamer_slug": "streamer-one"},
    )
    first_response = client.post(
        "/streamers/revenue-shares/record",
        headers=headers,
        json={
            "order_id": "saleor-order-1",
            "lines": [{"saleor_product_id": "product-1", "gross_amount": 1200}],
        },
    )

    replay_response = client.post(
        "/streamers/revenue-shares/record",
        headers=headers,
        json={
            "order_id": "saleor-order-1",
            "lines": [{"saleor_product_id": "product-1", "gross_amount": 1300}],
        },
    )

    assert first_response.status_code == 200
    assert replay_response.status_code == 409
    assert replay_response.json()["detail"] == "revenue share record conflict"


def signed_streamer_order_completed_request(
    client: TestClient,
    *,
    payload: dict,
    event_id: str = "evt-revenue-share-1",
    timestamp: int | None = None,
    secret: str = "shared-secret",
):
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = timestamp or int(time.time())
    signed_payload = f"{timestamp}.{event_id}.".encode() + body
    signature = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return client.post(
        "/streamers/webhooks/order-completed",
        headers={
            "Content-Type": "application/json",
            "X-Tachiya-Internal-Secret": secret,
            "X-Tachiya-Webhook-Event-Id": event_id,
            "X-Tachiya-Webhook-Timestamp": str(timestamp),
            "X-Tachiya-Webhook-Signature": signature,
        },
        content=body,
    )


def test_revenue_share_order_completed_webhook_records_shares(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    streamer_response = client.post(
        "/streamers",
        headers=headers,
        json={"slug": "streamer-one", "display_name": "One", "commission_bps": 1250},
    )
    client.post(
        "/streamers/product-assignments",
        headers=headers,
        json={"saleor_product_id": "product-1", "streamer_slug": "streamer-one"},
    )

    response = signed_streamer_order_completed_request(
        client,
        payload={
            "order_id": "saleor-order-1",
            "lines": [
                {"saleor_product_id": "product-1", "gross_amount": 1200},
                {"saleor_product_id": "missing-product", "gross_amount": 300},
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["order_id"] == "saleor-order-1"
    assert response.json()["unassigned_product_ids"] == ["missing-product"]
    assert response.json()["records"][0]["streamer_profile_id"] == streamer_response.json()["id"]
    assert response.json()["records"][0]["streamer_slug"] == "streamer-one"
    assert response.json()["records"][0]["share_amount"] == 150
    event = session.query(WebhookEvent).one()
    assert event.event_id == "evt-revenue-share-1"
    assert event.event_type == "revenue_share.order_completed"
    record = session.query(StreamerRevenueShareRecord).one()
    assert record.order_id == "saleor-order-1"
    assert record.share_amount == 150


def test_revenue_share_order_completed_webhook_rejects_missing_signature(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.post(
        "/streamers/webhooks/order-completed",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={
            "order_id": "saleor-order-1",
            "lines": [{"saleor_product_id": "product-1", "gross_amount": 1200}],
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid webhook signature"
    assert session.query(WebhookEvent).count() == 0
    assert session.query(StreamerRevenueShareRecord).count() == 0


def test_revenue_share_order_completed_webhook_rejects_replayed_event(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    client.post("/streamers", headers=headers, json={"slug": "streamer-one", "display_name": "One"})
    client.post(
        "/streamers/product-assignments",
        headers=headers,
        json={"saleor_product_id": "product-1", "streamer_slug": "streamer-one"},
    )
    payload = {
        "order_id": "saleor-order-1",
        "lines": [{"saleor_product_id": "product-1", "gross_amount": 1200}],
    }

    first_response = signed_streamer_order_completed_request(client, payload=payload)
    second_response = signed_streamer_order_completed_request(client, payload=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "webhook event already processed"
    assert session.query(WebhookEvent).count() == 1
    assert session.query(StreamerRevenueShareRecord).count() == 1


def test_revenue_share_order_completed_webhook_rejects_record_conflict(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    client.post("/streamers", headers=headers, json={"slug": "streamer-one", "display_name": "One"})
    client.post(
        "/streamers/product-assignments",
        headers=headers,
        json={"saleor_product_id": "product-1", "streamer_slug": "streamer-one"},
    )
    first_response = signed_streamer_order_completed_request(
        client,
        payload={
            "order_id": "saleor-order-1",
            "lines": [{"saleor_product_id": "product-1", "gross_amount": 1200}],
        },
        event_id="evt-revenue-share-1",
    )

    conflict_response = signed_streamer_order_completed_request(
        client,
        payload={
            "order_id": "saleor-order-1",
            "lines": [{"saleor_product_id": "product-1", "gross_amount": 1300}],
        },
        event_id="evt-revenue-share-2",
    )

    assert first_response.status_code == 200
    assert conflict_response.status_code == 409
    assert conflict_response.json()["detail"] == "revenue share record conflict"
    assert session.query(WebhookEvent).count() == 1
    assert session.query(StreamerRevenueShareRecord).count() == 1


def test_list_revenue_share_records(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    streamer_response = client.post(
        "/streamers",
        headers=headers,
        json={"slug": "streamer-one", "display_name": "One", "commission_bps": 1250},
    )
    client.post(
        "/streamers/product-assignments",
        headers=headers,
        json={"saleor_product_id": "product-1", "streamer_slug": "streamer-one"},
    )
    client.post(
        "/streamers/revenue-shares/record",
        headers=headers,
        json={
            "order_id": "order-1",
            "lines": [{"saleor_product_id": "product-1", "gross_amount": 1200}],
        },
    )

    response = client.get(
        "/streamers/revenue-shares/records?status=Pending&streamer_slug=streamer-one&limit=10",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["records"][0]["order_id"] == "order-1"
    assert response.json()["records"][0]["streamer_profile_id"] == streamer_response.json()["id"]
    assert response.json()["records"][0]["streamer_slug"] == "streamer-one"
    assert response.json()["records"][0]["share_amount"] == 150
    assert response.json()["records"][0]["status"] == "pending"
    assert response.json()["records"][0]["created_at"]
    assert response.json()["records"][0]["updated_at"]


def test_list_revenue_share_records_filters_created_range(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    client.post("/streamers", headers=headers, json={"slug": "streamer-one", "display_name": "One"})
    client.post(
        "/streamers/product-assignments",
        headers=headers,
        json={"saleor_product_id": "product-1", "streamer_slug": "streamer-one"},
    )
    for order_id in ["order-before", "order-start", "order-end", "order-after"]:
        client.post(
            "/streamers/revenue-shares/record",
            headers=headers,
            json={
                "order_id": order_id,
                "lines": [{"saleor_product_id": "product-1", "gross_amount": 1200}],
            },
        )
    records = {
        record.order_id: record
        for record in session.query(StreamerRevenueShareRecord).all()
    }
    records["order-before"].created_at = datetime(2026, 1, 1, 23, 59, 59)
    records["order-start"].created_at = datetime(2026, 1, 2, 0, 0, 0)
    records["order-end"].created_at = datetime(2026, 1, 3, 0, 0, 0)
    records["order-after"].created_at = datetime(2026, 1, 3, 0, 0, 1)
    session.commit()

    response = client.get(
        "/streamers/revenue-shares/records",
        headers=headers,
        params={
            "created_from": "2026-01-02T00:00:00",
            "created_to": "2026-01-03T00:00:00",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    assert [record["order_id"] for record in response.json()["records"]] == [
        "order-end",
        "order-start",
    ]


def test_list_revenue_share_records_rejects_invalid_query(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}

    invalid_limit_response = client.get(
        "/streamers/revenue-shares/records?limit=101",
        headers=headers,
    )
    invalid_status_response = client.get(
        "/streamers/revenue-shares/records?status=settled",
        headers=headers,
    )

    assert invalid_limit_response.status_code == 422
    assert invalid_status_response.status_code == 422
    assert invalid_status_response.json()["detail"] == "status must be pending, paid, or void"


def test_list_revenue_share_records_rejects_invalid_created_range(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/streamers/revenue-shares/records",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={
            "created_from": "2026-01-03T00:00:00",
            "created_to": "2026-01-02T00:00:00",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid created_at range"


def test_summarize_revenue_share_records(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    client.post("/streamers", headers=headers, json={"slug": "streamer-one", "display_name": "One"})
    client.post("/streamers", headers=headers, json={"slug": "streamer-two", "display_name": "Two"})
    client.post(
        "/streamers/product-assignments",
        headers=headers,
        json={"saleor_product_id": "product-1", "streamer_slug": "streamer-one"},
    )
    client.post(
        "/streamers/product-assignments",
        headers=headers,
        json={"saleor_product_id": "product-2", "streamer_slug": "streamer-two"},
    )
    paid_record_response = client.post(
        "/streamers/revenue-shares/record",
        headers=headers,
        json={
            "order_id": "order-1",
            "lines": [{"saleor_product_id": "product-1", "gross_amount": 1200}],
        },
    )
    client.post(
        f"/streamers/revenue-shares/records/{paid_record_response.json()['records'][0]['id']}/status",
        headers=headers,
        json={"status": " Paid "},
    )
    client.post(
        "/streamers/revenue-shares/record",
        headers=headers,
        json={
            "order_id": "order-2",
            "lines": [{"saleor_product_id": "product-2", "gross_amount": 2400}],
        },
    )

    response = client.get("/streamers/revenue-shares/summary", headers=headers)
    filtered_response = client.get(
        "/streamers/revenue-shares/summary?streamer_slug=streamer-two",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "summaries": [
            {"status": "paid", "record_count": 1, "gross_amount": 1200, "share_amount": 120},
            {"status": "pending", "record_count": 1, "gross_amount": 2400, "share_amount": 240},
        ],
    }
    assert filtered_response.status_code == 200
    assert filtered_response.json() == {
        "summaries": [
            {"status": "pending", "record_count": 1, "gross_amount": 2400, "share_amount": 240},
        ],
    }


def test_summarize_revenue_share_records_filters_created_range(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    client.post("/streamers", headers=headers, json={"slug": "streamer-one", "display_name": "One"})
    client.post(
        "/streamers/product-assignments",
        headers=headers,
        json={"saleor_product_id": "product-1", "streamer_slug": "streamer-one"},
    )
    for order_id in ["order-before", "order-in-range", "order-after"]:
        client.post(
            "/streamers/revenue-shares/record",
            headers=headers,
            json={
                "order_id": order_id,
                "lines": [{"saleor_product_id": "product-1", "gross_amount": 1200}],
            },
        )
    records = {
        record.order_id: record
        for record in session.query(StreamerRevenueShareRecord).all()
    }
    records["order-before"].created_at = datetime(2026, 1, 1, 23, 59, 59)
    records["order-in-range"].created_at = datetime(2026, 1, 2, 0, 0, 0)
    records["order-after"].created_at = datetime(2026, 1, 3, 0, 0, 1)
    session.commit()

    response = client.get(
        "/streamers/revenue-shares/summary",
        headers=headers,
        params={
            "created_from": "2026-01-02T00:00:00",
            "created_to": "2026-01-03T00:00:00",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "summaries": [
            {"status": "pending", "record_count": 1, "gross_amount": 1200, "share_amount": 120},
        ],
    }


def test_summarize_revenue_share_records_rejects_invalid_query(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/streamers/revenue-shares/summary?status=%20",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "status is required"


def test_summarize_revenue_share_records_rejects_invalid_created_range(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/streamers/revenue-shares/summary",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={
            "created_from": "2026-01-03T00:00:00",
            "created_to": "2026-01-02T00:00:00",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid created_at range"


def test_update_revenue_share_record_status(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    headers = {"X-Tachiya-Internal-Secret": "shared-secret"}
    client.post("/streamers", headers=headers, json={"slug": "streamer-one", "display_name": "One"})
    client.post(
        "/streamers/product-assignments",
        headers=headers,
        json={"saleor_product_id": "product-1", "streamer_slug": "streamer-one"},
    )
    record_response = client.post(
        "/streamers/revenue-shares/record",
        headers=headers,
        json={
            "order_id": "order-1",
            "lines": [{"saleor_product_id": "product-1", "gross_amount": 1200}],
        },
    )
    record_id = record_response.json()["records"][0]["id"]

    response = client.post(
        f"/streamers/revenue-shares/records/{record_id}/status",
        headers=headers,
        json={"status": "paid"},
    )

    assert response.status_code == 200
    assert response.json()["record"]["id"] == record_id
    assert response.json()["record"]["order_id"] == "order-1"
    assert response.json()["record"]["status"] == "paid"
    assert response.json()["record"]["created_at"]
    assert response.json()["record"]["updated_at"]


def test_update_revenue_share_record_status_rejects_missing_record(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.post(
        "/streamers/revenue-shares/records/missing-record/status",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={"status": "paid"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "revenue share record not found"


def test_update_revenue_share_record_status_rejects_invalid_status(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.post(
        "/streamers/revenue-shares/records/record-1/status",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={"status": "pending"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "status must be paid or void"
