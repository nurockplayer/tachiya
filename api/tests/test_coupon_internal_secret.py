import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from routers import coupons


class FakeDB:
    def __init__(self):
        self.records = []
        self.commits = 0

    def add(self, record):
        self.records.append(record)

    def commit(self):
        self.commits += 1


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
    assert fake_db.records[0].saleor_voucher_id == "saleor-voucher-1"
    assert fake_db.commits == 1
