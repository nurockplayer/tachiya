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
