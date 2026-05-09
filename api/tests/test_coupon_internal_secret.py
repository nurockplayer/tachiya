import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
    assert response.json()["voucher_code"].startswith("DEMO-")
    assert response.json()["redemption_token"]
    assert fake_db.records[0].redemption_token == response.json()["redemption_token"]
    assert fake_db.records[0].saleor_voucher_id == "saleor-voucher-1"
    assert fake_db.commits == 1


def test_redeem_reuses_existing_coupon_for_same_idempotency_key(monkeypatch):
    existing_coupon = SimpleNamespace(
        voucher_code="DEMO-EXISTING",
        redemption_token="token-existing",
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
    assert fake_db.records == []
    assert fake_db.commits == 0


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


def test_list_coupons_returns_empty_for_unknown_redemption_token():
    fake_db = FakeDB(existing_coupon=None)
    client = build_client(fake_db)

    response = client.get("/coupons", params={"redemption_token": "missing-token"})

    assert response.status_code == 200
    assert response.json() == []
