import sys
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.coupon import UserCoupon
from models.coupon_redemption_audit import CouponRedemptionAuditEvent
from routers import coupons


class FakeDB:
    def __init__(self, existing_coupon=None, list_coupons=None):
        self.records = []
        self.commits = 0
        self.existing_coupon = existing_coupon
        self.list_coupons = list_coupons or []

    def add(self, record):
        self.records.append(record)

    def commit(self):
        self.commits += 1

    def query(self, model):
        return FakeQuery(self.existing_coupon, self.list_coupons)


class FakeQuery:
    def __init__(self, existing_coupon, list_coupons):
        self.existing_coupon = existing_coupon
        self.list_coupons = list_coupons

    def filter(self, *criteria):
        return self

    def order_by(self, *criteria):
        return self

    def limit(self, limit):
        return self

    def first(self):
        return self.existing_coupon

    def all(self):
        return self.list_coupons


def build_client(fake_db: FakeDB) -> TestClient:
    app = FastAPI()
    app.include_router(coupons.router)

    def override_db():
        yield fake_db

    app.dependency_overrides[coupons.get_db] = override_db
    return TestClient(app)


def build_real_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_redeem_rejects_missing_internal_secret(monkeypatch):
    fake_db = FakeDB()
    client = build_client(fake_db)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    def fail_create_voucher(coupon_id: str, code: str):
        raise AssertionError("create_voucher should not be called")

    monkeypatch.setattr(coupons, "create_voucher", fail_create_voucher)

    response = client.post(
        "/coupons/redeem",
        json={"coupon_id": "tachiya-95", "tcg_cost": 18},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid internal secret"
    assert fake_db.records == []
    assert fake_db.commits == 0


def test_redeem_rejects_wrong_internal_secret(monkeypatch):
    fake_db = FakeDB()
    client = build_client(fake_db)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    def fail_create_voucher(coupon_id: str, code: str):
        raise AssertionError("create_voucher should not be called")

    monkeypatch.setattr(coupons, "create_voucher", fail_create_voucher)

    response = client.post(
        "/coupons/redeem",
        headers={"X-Tachiya-Internal-Secret": "wrong-secret"},
        json={"coupon_id": "tachiya-95", "tcg_cost": 18},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid internal secret"
    assert fake_db.records == []
    assert fake_db.commits == 0


def test_redeem_accepts_matching_internal_secret(monkeypatch):
    fake_db = FakeDB()
    client = build_client(fake_db)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    def fake_create_voucher(coupon_id: str, code: str):
        return {"code": code, "voucher_id": "saleor-voucher-1"}

    monkeypatch.setattr(coupons, "create_voucher", fake_create_voucher)

    response = client.post(
        "/coupons/redeem",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={"coupon_id": "tachiya-95", "tcg_cost": 18},
    )

    assert response.status_code == 200
    assert response.json()["voucher_code"].startswith("TACHIYA-")
    assert response.json()["redemption_token"]
    assert fake_db.records[0].redemption_token == response.json()["redemption_token"]
    assert fake_db.records[0].saleor_voucher_id == "saleor-voucher-1"
    assert fake_db.commits == 1


def test_redeem_normalizes_coupon_id_and_idempotency_key(monkeypatch):
    fake_db = FakeDB()
    client = build_client(fake_db)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    def fake_create_voucher(coupon_id: str, code: str):
        assert coupon_id == "tachiya-95"
        return {"code": code, "voucher_id": "saleor-voucher-1"}

    monkeypatch.setattr(coupons, "create_voucher", fake_create_voucher)

    response = client.post(
        "/coupons/redeem",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={
            "coupon_id": " tachiya-95 ",
            "tcg_cost": 18,
            "idempotency_key": " redeem-1 ",
        },
    )

    assert response.status_code == 200
    assert fake_db.records[0].coupon_id == "tachiya-95"
    assert fake_db.records[0].idempotency_key == "redeem-1"
    assert fake_db.records[1].coupon_id == "tachiya-95"
    assert fake_db.records[1].idempotency_key == "redeem-1"


def test_redeem_rejects_blank_coupon_id(monkeypatch):
    fake_db = FakeDB()
    client = build_client(fake_db)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    def fail_create_voucher(coupon_id: str, code: str):
        raise AssertionError("create_voucher should not be called")

    monkeypatch.setattr(coupons, "create_voucher", fail_create_voucher)

    response = client.post(
        "/coupons/redeem",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={"coupon_id": " ", "tcg_cost": 18},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "coupon_id is required"
    assert fake_db.records[0].status == "failed"
    assert fake_db.records[0].reason == "coupon_id is required"


def test_redeem_treats_blank_idempotency_key_as_missing(monkeypatch):
    fake_db = FakeDB()
    client = build_client(fake_db)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    def fake_create_voucher(coupon_id: str, code: str):
        return {"code": code, "voucher_id": "saleor-voucher-1"}

    monkeypatch.setattr(coupons, "create_voucher", fake_create_voucher)

    response = client.post(
        "/coupons/redeem",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={"coupon_id": "tachiya-95", "tcg_cost": 18, "idempotency_key": " "},
    )

    assert response.status_code == 200
    assert fake_db.records[0].idempotency_key is None
    assert fake_db.records[1].idempotency_key is None


def test_redeem_uses_configured_voucher_code_prefix(monkeypatch):
    fake_db = FakeDB()
    client = build_client(fake_db)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    monkeypatch.setenv("TACHIYA_VOUCHER_CODE_PREFIX", " live-drop ")

    def fake_create_voucher(coupon_id: str, code: str):
        return {"code": code, "voucher_id": "saleor-voucher-1"}

    monkeypatch.setattr(coupons, "create_voucher", fake_create_voucher)

    response = client.post(
        "/coupons/redeem",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={"coupon_id": "tachiya-95", "tcg_cost": 18},
    )

    assert response.status_code == 200
    assert response.json()["voucher_code"].startswith("LIVE-DROP-")


def test_redeem_rejects_mismatched_tcg_cost_before_saleor(monkeypatch):
    fake_db = FakeDB()
    client = build_client(fake_db)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    called = False

    def fake_create_voucher(coupon_id: str, code: str):
        nonlocal called
        called = True
        return {"code": code, "voucher_id": "saleor-voucher-1"}

    monkeypatch.setattr(coupons, "create_voucher", fake_create_voucher)

    response = client.post(
        "/coupons/redeem",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={"coupon_id": "tachiya-95", "tcg_cost": 1},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "tcg_cost mismatch for coupon_id: tachiya-95"
    assert called is False
    assert fake_db.records[0].status == "failed"
    assert fake_db.records[0].reason == "tcg_cost mismatch: expected 18, got 1"
    assert fake_db.commits == 1


def test_redeem_rejects_non_positive_tcg_cost_before_saleor(monkeypatch):
    fake_db = FakeDB()
    client = build_client(fake_db)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    called = False

    def fake_create_voucher(coupon_id: str, code: str):
        nonlocal called
        called = True
        return {"code": code, "voucher_id": "saleor-voucher-1"}

    monkeypatch.setattr(coupons, "create_voucher", fake_create_voucher)

    response = client.post(
        "/coupons/redeem",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={"coupon_id": "tachiya-95", "tcg_cost": 0},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "tcg_cost must be positive"
    assert called is False
    assert fake_db.records[0].status == "failed"
    assert fake_db.records[0].reason == "tcg_cost must be positive"
    assert fake_db.commits == 1


def test_redeem_reuses_existing_coupon_for_same_idempotency_key(monkeypatch):
    existing_coupon = SimpleNamespace(
        coupon_id="tachiya-95",
        voucher_code="DEMO-EXISTING",
        redemption_token="token-existing",
        tcg_cost=18,
    )
    fake_db = FakeDB(existing_coupon=existing_coupon)
    client = build_client(fake_db)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    def fail_create_voucher(coupon_id: str, code: str):
        raise AssertionError("create_voucher should not be called")

    monkeypatch.setattr(coupons, "create_voucher", fail_create_voucher)

    response = client.post(
        "/coupons/redeem",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={
            "coupon_id": "tachiya-95",
            "tcg_cost": 18,
            "idempotency_key": "redeem-1",
        },
    )

    assert response.status_code == 200
    assert response.json()["voucher_code"] == "DEMO-EXISTING"
    assert response.json()["redemption_token"] == "token-existing"
    assert fake_db.records[0].status == "replayed"
    assert fake_db.records[0].redemption_token == "token-existing"
    assert fake_db.commits == 1


def test_redeem_rejects_mismatched_idempotency_replay(monkeypatch):
    existing_coupon = SimpleNamespace(
        coupon_id="tachiya-95",
        voucher_code="DEMO-EXISTING",
        redemption_token="token-existing",
        tcg_cost=18,
    )
    fake_db = FakeDB(existing_coupon=existing_coupon)
    client = build_client(fake_db)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    def fail_create_voucher(coupon_id: str, code: str):
        raise AssertionError("create_voucher should not be called")

    monkeypatch.setattr(coupons, "create_voucher", fail_create_voucher)

    response = client.post(
        "/coupons/redeem",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={
            "coupon_id": "free-ship",
            "tcg_cost": 30,
            "idempotency_key": "redeem-1",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "idempotency key conflict"
    assert fake_db.records[0].status == "failed"
    assert fake_db.records[0].reason == "idempotency key conflict"
    assert fake_db.commits == 1


def test_redeem_persists_idempotency_key_on_first_request(monkeypatch):
    fake_db = FakeDB()
    client = build_client(fake_db)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    def fake_create_voucher(coupon_id: str, code: str):
        return {"code": code, "voucher_id": "saleor-voucher-1"}

    monkeypatch.setattr(coupons, "create_voucher", fake_create_voucher)

    response = client.post(
        "/coupons/redeem",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={
            "coupon_id": "tachiya-95",
            "tcg_cost": 18,
            "idempotency_key": "redeem-1",
        },
    )

    assert response.status_code == 200
    assert fake_db.records[0].idempotency_key == "redeem-1"
    assert fake_db.records[1].status == "succeeded"
    assert fake_db.records[1].idempotency_key == "redeem-1"
    assert fake_db.commits == 1


def test_redeem_records_failed_audit_when_saleor_voucher_fails(monkeypatch):
    fake_db = FakeDB()
    client = build_client(fake_db)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    def fail_create_voucher(coupon_id: str, code: str):
        raise RuntimeError("saleor unavailable")

    monkeypatch.setattr(coupons, "create_voucher", fail_create_voucher)

    response = client.post(
        "/coupons/redeem",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={
            "coupon_id": "tachiya-95",
            "tcg_cost": 18,
            "idempotency_key": "redeem-1",
        },
    )

    assert response.status_code == 500
    assert fake_db.records[0].status == "failed"
    assert fake_db.records[0].reason == "saleor unavailable"
    assert fake_db.commits == 1


def test_list_coupons_filters_by_redemption_token():
    matching_coupon = SimpleNamespace(
        voucher_code="DEMO-MATCH",
        coupon_type="PERCENT_5",
        tcg_cost=18,
        status="active",
    )
    fake_db = FakeDB(existing_coupon=matching_coupon)
    client = build_client(fake_db)

    response = client.get("/coupons", params={"redemption_token": "token-1"})

    assert response.status_code == 200
    assert response.json() == [
        {
            "voucher_code": "DEMO-MATCH",
            "coupon_type": "PERCENT_5",
            "tcg_cost": 18,
            "status": "active",
        }
    ]


def test_list_coupons_normalizes_redemption_token():
    session = build_real_session()
    session.add(
        UserCoupon(
            id="matching-coupon",
            coupon_id="tachiya-95",
            voucher_code="TACHIYA-ABC123",
            saleor_voucher_id="saleor-1",
            redemption_token="token-1",
            coupon_type="PERCENT_5",
            tcg_cost=18,
            status="active",
            created_at=datetime(2026, 1, 2, 0, 0, 0),
        ),
    )
    session.commit()
    client = build_client(session)

    response = client.get("/coupons", params={"redemption_token": " token-1 "})

    assert response.status_code == 200
    assert response.json()[0]["voucher_code"] == "TACHIYA-ABC123"


def test_list_coupons_returns_empty_for_unknown_redemption_token():
    fake_db = FakeDB(existing_coupon=None)
    client = build_client(fake_db)

    response = client.get("/coupons", params={"redemption_token": "missing-token"})

    assert response.status_code == 200
    assert response.json() == []


def test_list_coupons_requires_redemption_token():
    matching_coupon = SimpleNamespace(
        voucher_code="TACHIYA-MATCH",
        coupon_type="PERCENT_5",
        tcg_cost=18,
        status="active",
    )
    fake_db = FakeDB(list_coupons=[matching_coupon])
    client = build_client(fake_db)

    response = client.get("/coupons")

    assert response.status_code == 400
    assert response.json()["detail"] == "redemption_token is required"


def test_list_coupons_rejects_blank_redemption_token():
    fake_db = FakeDB()
    client = build_client(fake_db)

    response = client.get("/coupons", params={"redemption_token": " "})

    assert response.status_code == 400
    assert response.json()["detail"] == "redemption_token is required"


def test_coupon_created_at_default_uses_naive_utc():
    session = build_real_session()
    coupon = UserCoupon(
        id="default-created-at",
        coupon_id="tachiya-95",
        voucher_code="TACHIYA-DEFAULT",
        saleor_voucher_id="saleor-default",
        redemption_token="token-default",
        coupon_type="PERCENT_5",
        tcg_cost=18,
        status="active",
    )
    session.add(coupon)
    session.commit()
    session.refresh(coupon)

    assert coupon.created_at is not None
    assert coupon.created_at.tzinfo is None


def test_list_redemption_audit_events_requires_internal_secret(monkeypatch):
    fake_db = FakeDB()
    client = build_client(fake_db)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get("/coupons/redemption-audit-events")

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid internal secret"


def test_list_redemption_audit_events_returns_recent_events(monkeypatch):
    event = SimpleNamespace(
        coupon_id="tachiya-95",
        idempotency_key="redeem-1",
        redemption_token="token-1",
        status="succeeded",
        reason=None,
        created_at="2026-01-01T00:00:00",
    )
    fake_db = FakeDB(list_coupons=[event])
    client = build_client(fake_db)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/coupons/redemption-audit-events",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
    )

    assert response.status_code == 200
    assert response.json()["events"][0] == {
        "coupon_id": "tachiya-95",
        "idempotency_key": "redeem-1",
        "redemption_token": "token-1",
        "status": "succeeded",
        "reason": None,
        "created_at": "2026-01-01T00:00:00",
    }


def test_list_redemption_audit_events_filters_fields_and_created_range(monkeypatch):
    session = build_real_session()
    session.add_all(
        [
            CouponRedemptionAuditEvent(
                id="before-range",
                coupon_id="tachiya-95",
                idempotency_key="redeem-before",
                redemption_token="token-before",
                status="failed",
                reason="before",
                created_at=datetime(2026, 1, 1, 23, 59, 59),
            ),
            CouponRedemptionAuditEvent(
                id="matching-old",
                coupon_id="tachiya-95",
                idempotency_key="redeem-1",
                redemption_token="token-1",
                status="failed",
                reason="older match",
                created_at=datetime(2026, 1, 2, 0, 0, 0),
            ),
            CouponRedemptionAuditEvent(
                id="matching-new",
                coupon_id="tachiya-95",
                idempotency_key="redeem-1",
                redemption_token="token-1",
                status="failed",
                reason="newer match",
                created_at=datetime(2026, 1, 3, 0, 0, 0),
            ),
            CouponRedemptionAuditEvent(
                id="wrong-status",
                coupon_id="tachiya-95",
                idempotency_key="redeem-1",
                redemption_token="token-1",
                status="succeeded",
                reason=None,
                created_at=datetime(2026, 1, 2, 12, 0, 0),
            ),
            CouponRedemptionAuditEvent(
                id="after-range",
                coupon_id="tachiya-95",
                idempotency_key="redeem-1",
                redemption_token="token-1",
                status="failed",
                reason="after",
                created_at=datetime(2026, 1, 3, 0, 0, 1),
            ),
        ],
    )
    session.commit()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/coupons/redemption-audit-events",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={
            "coupon_id": " tachiya-95 ",
            "status": " failed ",
            "idempotency_key": " redeem-1 ",
            "redemption_token": " token-1 ",
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


def test_list_redemption_audit_events_rejects_invalid_created_range(monkeypatch):
    fake_db = FakeDB()
    client = build_client(fake_db)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/coupons/redemption-audit-events",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={
            "created_from": "2026-01-03T00:00:00",
            "created_to": "2026-01-02T00:00:00",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid created_at range"


def test_list_redemption_audit_events_rejects_blank_filter(monkeypatch):
    fake_db = FakeDB()
    client = build_client(fake_db)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/coupons/redemption-audit-events",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"coupon_id": " "},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "coupon_id is required"


def test_list_admin_coupons_requires_internal_secret(monkeypatch):
    fake_db = FakeDB()
    client = build_client(fake_db)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get("/coupons/admin")

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid internal secret"


def test_list_admin_coupons_returns_recent_coupons(monkeypatch):
    coupon = SimpleNamespace(
        coupon_id="tachiya-95",
        voucher_code="TACHIYA-ABC123",
        coupon_type="PERCENT_5",
        tcg_cost=18,
        status="active",
        redemption_token="token-1",
        created_at="2026-01-01T00:00:00",
    )
    fake_db = FakeDB(list_coupons=[coupon])
    client = build_client(fake_db)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/coupons/admin",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"status": " active "},
    )

    assert response.status_code == 200
    assert response.json()["coupons"] == [
        {
            "coupon_id": "tachiya-95",
            "voucher_code": "TACHIYA-ABC123",
            "coupon_type": "PERCENT_5",
            "tcg_cost": 18,
            "status": "active",
            "redemption_token": "token-1",
            "created_at": "2026-01-01T00:00:00",
        },
    ]


def test_list_admin_coupons_filters_created_range(monkeypatch):
    session = build_real_session()
    session.add_all(
        [
            UserCoupon(
                id="before-range",
                coupon_id="tachiya-95",
                voucher_code="TACHIYA-BEFORE",
                saleor_voucher_id="saleor-before",
                redemption_token="token-before",
                coupon_type="PERCENT_5",
                tcg_cost=18,
                status="active",
                created_at=datetime(2026, 1, 1, 23, 59, 59),
            ),
            UserCoupon(
                id="range-start",
                coupon_id="tachiya-95",
                voucher_code="TACHIYA-START",
                saleor_voucher_id="saleor-start",
                redemption_token="token-start",
                coupon_type="PERCENT_5",
                tcg_cost=18,
                status="active",
                created_at=datetime(2026, 1, 2, 0, 0, 0),
            ),
            UserCoupon(
                id="range-end",
                coupon_id="tachiya-100",
                voucher_code="TACHIYA-END",
                saleor_voucher_id="saleor-end",
                redemption_token="token-end",
                coupon_type="PERCENT_10",
                tcg_cost=35,
                status="redeemed",
                created_at=datetime(2026, 1, 3, 0, 0, 0),
            ),
            UserCoupon(
                id="after-range",
                coupon_id="tachiya-95",
                voucher_code="TACHIYA-AFTER",
                saleor_voucher_id="saleor-after",
                redemption_token="token-after",
                coupon_type="PERCENT_5",
                tcg_cost=18,
                status="active",
                created_at=datetime(2026, 1, 3, 0, 0, 1),
            ),
        ],
    )
    session.commit()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/coupons/admin",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={
            "created_from": "2026-01-02T00:00:00",
            "created_to": "2026-01-03T00:00:00",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    assert [coupon["voucher_code"] for coupon in response.json()["coupons"]] == [
        "TACHIYA-END",
        "TACHIYA-START",
    ]


def test_list_admin_coupons_filters_exact_lookup_fields(monkeypatch):
    session = build_real_session()
    session.add_all(
        [
            UserCoupon(
                id="matching-coupon",
                coupon_id="tachiya-95",
                voucher_code="TACHIYA-MATCH",
                saleor_voucher_id="saleor-match",
                redemption_token="token-match",
                coupon_type="PERCENT_5",
                tcg_cost=18,
                status="active",
                created_at=datetime(2026, 1, 2, 0, 0, 0),
            ),
            UserCoupon(
                id="other-coupon",
                coupon_id="tachiya-95",
                voucher_code="TACHIYA-OTHER",
                saleor_voucher_id="saleor-other",
                redemption_token="token-other",
                coupon_type="PERCENT_5",
                tcg_cost=18,
                status="active",
                created_at=datetime(2026, 1, 2, 0, 0, 1),
            ),
        ],
    )
    session.commit()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/coupons/admin",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={
            "coupon_id": " tachiya-95 ",
            "voucher_code": " TACHIYA-MATCH ",
            "redemption_token": " token-match ",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    assert [coupon["voucher_code"] for coupon in response.json()["coupons"]] == [
        "TACHIYA-MATCH",
    ]


def test_list_admin_coupons_rejects_blank_status(monkeypatch):
    fake_db = FakeDB()
    client = build_client(fake_db)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/coupons/admin",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"status": " "},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "status is required"


def test_list_admin_coupons_rejects_blank_exact_lookup_filter(monkeypatch):
    fake_db = FakeDB()
    client = build_client(fake_db)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    for field, message in [
        ("coupon_id", "coupon_id is required"),
        ("voucher_code", "voucher_code is required"),
        ("redemption_token", "redemption_token is required"),
    ]:
        response = client.get(
            "/coupons/admin",
            headers={"X-Tachiya-Internal-Secret": "shared-secret"},
            params={field: " "},
        )

        assert response.status_code == 422
        assert response.json()["detail"] == message


def test_list_admin_coupons_rejects_invalid_created_range(monkeypatch):
    fake_db = FakeDB()
    client = build_client(fake_db)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/coupons/admin",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={
            "created_from": "2026-01-03T00:00:00",
            "created_to": "2026-01-02T00:00:00",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid created_at range"
