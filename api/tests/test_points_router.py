import asyncio
import hashlib
import hmac
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from conftest import build_router_client, build_sqlite_session
from models.points_ledger import PointsLedger
from models.webhook_event import WebhookEvent
from routers import points
from services.points_service import PointsService


def build_session():
    return build_sqlite_session(static_pool=True)


def build_client(session) -> TestClient:
    return build_router_client(points.router, points.get_db, session)


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


def test_points_balance_trims_user_id(monkeypatch):
    session = build_session()
    asyncio.run(PointsService(session).credit("user-1", 120, "order-1"))
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/points/balance",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"user_id": " user-1 "},
    )

    assert response.status_code == 200
    assert response.json() == {"user_id": "user-1", "balance": 120}


def test_points_balance_rejects_blank_user_id(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/points/balance",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"user_id": " "},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "user_id is required"


def test_points_balance_excludes_expired_credit(monkeypatch):
    session = build_session()
    session.add_all(
        [
            PointsLedger(
                id="expired-credit",
                user_id="user-1",
                amount=120,
                entry_type="credit",
                source_type="tachigo",
                reference_id="tachigo:expired",
                expires_at=datetime(2000, 1, 1, 0, 0, 0),
                created_at=datetime(1999, 12, 1, 0, 0, 0),
            ),
            PointsLedger(
                id="active-credit",
                user_id="user-1",
                amount=40,
                entry_type="credit",
                source_type="manual",
                reference_id="manual:active",
                expires_at=datetime(2999, 12, 31, 23, 59, 59),
                created_at=datetime(2026, 1, 1, 0, 0, 0),
            ),
        ],
    )
    session.commit()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/points/balance",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"user_id": "user-1"},
    )

    assert response.status_code == 200
    assert response.json() == {"user_id": "user-1", "balance": 40}


def test_points_balance_rejects_missing_internal_secret(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get("/points/balance", params={"user_id": "user-1"})

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid internal secret"


def test_points_transaction_requires_internal_secret(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.post(
        "/points/transactions",
        json={
            "user_id": "user-1",
            "entry_type": "credit",
            "amount": 120,
            "reference_id": "order-1",
            "source_type": "order-reward",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid internal secret"


def test_points_transaction_creates_credit_and_returns_balance(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.post(
        "/points/transactions",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={
            "user_id": "user-1",
            "entry_type": "credit",
            "amount": 120,
            "reference_id": "order-1",
            "source_type": "order-reward",
            "expires_at": "2026-12-31T23:59:59",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["balance"] == 120
    assert body["entry"] == {
        "id": body["entry"]["id"],
        "amount": 120,
        "entry_type": "credit",
        "source_type": "order-reward",
        "reference_id": "order-1",
        "expires_at": "2026-12-31T23:59:59",
        "created_at": body["entry"]["created_at"],
    }


def test_points_transaction_uses_normalized_user_for_credit_balance(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.post(
        "/points/transactions",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={
            "user_id": " user-1 ",
            "entry_type": "credit",
            "amount": 120,
            "reference_id": "order-1",
            "source_type": "order-reward",
        },
    )

    assert response.status_code == 200
    assert response.json()["balance"] == 120
    assert asyncio.run(PointsService(session).get_balance("user-1")) == 120


def test_points_transaction_creates_debit_and_returns_balance(monkeypatch):
    session = build_session()
    asyncio.run(PointsService(session).credit("user-1", 120, "order-1"))
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.post(
        "/points/transactions",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={
            "user_id": "user-1",
            "entry_type": "debit",
            "amount": 45,
            "reference_id": "checkout-1",
            "source_type": "checkout",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["balance"] == 75
    assert body["entry"]["amount"] == -45
    assert body["entry"]["entry_type"] == "debit"
    assert body["entry"]["source_type"] == "checkout"
    assert body["entry"]["reference_id"] == "checkout-1"


def test_points_transaction_uses_normalized_user_for_debit_balance(monkeypatch):
    session = build_session()
    asyncio.run(PointsService(session).credit("user-1", 120, "order-1"))
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.post(
        "/points/transactions",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={
            "user_id": " user-1 ",
            "entry_type": "debit",
            "amount": 45,
            "reference_id": "checkout-1",
            "source_type": "checkout",
        },
    )

    assert response.status_code == 200
    assert response.json()["balance"] == 75
    assert asyncio.run(PointsService(session).get_balance("user-1")) == 75


def test_points_transaction_replays_same_reference(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    payload = {
        "user_id": "user-1",
        "entry_type": "credit",
        "amount": 120,
        "reference_id": "order-1",
        "source_type": "order-reward",
    }

    first = client.post(
        "/points/transactions",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json=payload,
    )
    second = client.post(
        "/points/transactions",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json=payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["entry"]["id"] == first.json()["entry"]["id"]
    assert second.json()["balance"] == 120
    assert session.query(PointsLedger).count() == 1


def test_points_transaction_rejects_insufficient_balance(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.post(
        "/points/transactions",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={
            "user_id": "user-1",
            "entry_type": "debit",
            "amount": 45,
            "reference_id": "checkout-1",
            "source_type": "checkout",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "insufficient balance"
    assert session.query(PointsLedger).count() == 0


def test_points_transaction_rejects_expired_credit_balance(monkeypatch):
    session = build_session()
    session.add(
        PointsLedger(
            id="expired-credit",
            user_id="user-1",
            amount=45,
            entry_type="credit",
            source_type="tachigo",
            reference_id="tachigo:expired",
            expires_at=datetime(2000, 1, 1, 0, 0, 0),
            created_at=datetime(1999, 12, 1, 0, 0, 0),
        ),
    )
    session.commit()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.post(
        "/points/transactions",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={
            "user_id": "user-1",
            "entry_type": "debit",
            "amount": 1,
            "reference_id": "checkout-1",
            "source_type": "checkout",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "insufficient balance"
    assert session.query(PointsLedger).count() == 1


def test_points_transaction_rejects_blank_user_id(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.post(
        "/points/transactions",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={
            "user_id": "",
            "entry_type": "credit",
            "amount": 120,
            "reference_id": "order-1",
            "source_type": "order-reward",
        },
    )

    assert response.status_code == 422
    assert session.query(PointsLedger).count() == 0


@pytest.mark.parametrize("field", ["user_id", "reference_id", "source_type"])
def test_points_transaction_rejects_whitespace_strings_at_schema(monkeypatch, field):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    payload = {
        "user_id": "user-1",
        "entry_type": "credit",
        "amount": 120,
        "reference_id": "order-1",
        "source_type": "order-reward",
    }
    payload[field] = "   "

    response = client.post(
        "/points/transactions",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json=payload,
    )

    assert response.status_code == 422
    assert session.query(PointsLedger).count() == 0


def test_points_transaction_rejects_non_positive_amount_at_schema(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.post(
        "/points/transactions",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={
            "user_id": "user-1",
            "entry_type": "credit",
            "amount": 0,
            "reference_id": "order-1",
            "source_type": "order-reward",
        },
    )

    assert response.status_code == 422
    assert session.query(PointsLedger).count() == 0


@pytest.mark.parametrize("amount", [True, "120"])
def test_points_transaction_rejects_non_strict_amount_at_schema(monkeypatch, amount):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.post(
        "/points/transactions",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={
            "user_id": "user-1",
            "entry_type": "credit",
            "amount": amount,
            "reference_id": "order-1",
            "source_type": "order-reward",
        },
    )

    assert response.status_code == 422
    assert session.query(PointsLedger).count() == 0


def test_points_transaction_rejects_invalid_entry_type(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.post(
        "/points/transactions",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={
            "user_id": "user-1",
            "entry_type": "adjust",
            "amount": 120,
            "reference_id": "order-1",
        },
    )

    assert response.status_code == 422


def signed_order_reward_request(
    client: TestClient,
    *,
    payload: dict,
    event_id: str = "evt-order-reward-1",
    timestamp: int | None = None,
    secret: str = "shared-secret",
):
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = timestamp or int(time.time())
    signed_payload = f"{timestamp}.{event_id}.".encode() + body
    signature = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return client.post(
        "/points/webhooks/order-rewarded",
        headers={
            "Content-Type": "application/json",
            "X-Tachiya-Internal-Secret": secret,
            "X-Tachiya-Webhook-Event-Id": event_id,
            "X-Tachiya-Webhook-Timestamp": str(timestamp),
            "X-Tachiya-Webhook-Signature": signature,
        },
        content=body,
    )


def test_order_reward_webhook_credits_customer_points(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = signed_order_reward_request(
        client,
        payload={
            "order_id": "order-1",
            "user_id": "saleor-user-1",
            "reward_points": 120,
        },
    )

    assert response.status_code == 200
    assert response.json()["rewarded"] is True
    assert response.json()["reward_points"] == 120
    assert response.json()["ledger_entry_id"]
    event = session.query(WebhookEvent).one()
    assert event.event_id == "evt-order-reward-1"
    assert event.event_type == "points.order_rewarded"
    ledger_entry = session.query(PointsLedger).one()
    assert ledger_entry.user_id == "saleor-user-1"
    assert ledger_entry.amount == 120
    assert ledger_entry.source_type == "order-reward"
    assert ledger_entry.reference_id == "order-reward:order-1"


def test_order_reward_webhook_trims_order_id_for_reference(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = signed_order_reward_request(
        client,
        payload={
            "order_id": " order-1 ",
            "user_id": "saleor-user-1",
            "reward_points": 120,
        },
    )

    assert response.status_code == 200
    ledger_entry = session.query(PointsLedger).one()
    assert ledger_entry.reference_id == "order-reward:order-1"


def test_order_reward_webhook_rejects_missing_signature_headers(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.post(
        "/points/webhooks/order-rewarded",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={
            "order_id": "order-1",
            "user_id": "saleor-user-1",
            "reward_points": 120,
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid webhook signature"
    assert session.query(WebhookEvent).count() == 0
    assert session.query(PointsLedger).count() == 0


def test_order_reward_webhook_rejects_replayed_event(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    payload = {
        "order_id": "order-1",
        "user_id": "saleor-user-1",
        "reward_points": 120,
    }

    first_response = signed_order_reward_request(client, payload=payload)
    second_response = signed_order_reward_request(client, payload=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "webhook event already processed"
    assert session.query(WebhookEvent).count() == 1
    assert session.query(PointsLedger).count() == 1


def test_order_reward_webhook_rejects_non_positive_reward_points(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = signed_order_reward_request(
        client,
        payload={
            "order_id": "order-1",
            "user_id": "saleor-user-1",
            "reward_points": 0,
        },
    )

    assert response.status_code == 422
    assert session.query(WebhookEvent).count() == 0
    assert session.query(PointsLedger).count() == 0


@pytest.mark.parametrize("reward_points", [True, "120"])
def test_order_reward_webhook_rejects_non_strict_reward_points(monkeypatch, reward_points):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = signed_order_reward_request(
        client,
        payload={
            "order_id": "order-1",
            "user_id": "saleor-user-1",
            "reward_points": reward_points,
        },
    )

    assert response.status_code == 422
    assert session.query(WebhookEvent).count() == 0
    assert session.query(PointsLedger).count() == 0


def test_order_reward_webhook_rejects_blank_order_id(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = signed_order_reward_request(
        client,
        payload={
            "order_id": "",
            "user_id": "saleor-user-1",
            "reward_points": 120,
        },
    )

    assert response.status_code == 422
    assert session.query(WebhookEvent).count() == 0
    assert session.query(PointsLedger).count() == 0


def test_order_reward_webhook_rejects_whitespace_user_id_at_schema(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = signed_order_reward_request(
        client,
        payload={
            "order_id": "order-1",
            "user_id": "   ",
            "reward_points": 120,
        },
    )

    assert response.status_code == 422
    assert session.query(WebhookEvent).count() == 0
    assert session.query(PointsLedger).count() == 0


def test_order_reward_webhook_rejects_whitespace_order_id(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = signed_order_reward_request(
        client,
        payload={
            "order_id": " ",
            "user_id": "saleor-user-1",
            "reward_points": 120,
        },
    )

    assert response.status_code == 422
    assert session.query(WebhookEvent).count() == 0
    assert session.query(PointsLedger).count() == 0


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


def test_points_ledger_trims_user_id(monkeypatch):
    session = build_session()
    session.add(
        PointsLedger(
            id="entry-1",
            user_id="user-1",
            amount=120,
            entry_type="credit",
            source_type="tachigo",
            reference_id="tachigo:redemption-1",
            created_at=datetime(2026, 1, 1, 0, 0, 0),
        ),
    )
    session.commit()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/points/ledger",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"user_id": " user-1 "},
    )

    assert response.status_code == 200
    assert response.json()["user_id"] == "user-1"
    assert [entry["id"] for entry in response.json()["entries"]] == ["entry-1"]


def test_points_ledger_rejects_blank_user_id(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/points/ledger",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"user_id": " "},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "user_id is required"


def test_points_ledger_admin_entries_filter_across_users(monkeypatch):
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
                user_id="user-2",
                amount=80,
                entry_type="credit",
                source_type="tachigo",
                reference_id="tachigo:redemption-2",
                created_at=datetime(2026, 1, 2, 0, 0, 0),
            ),
            PointsLedger(
                id="checkout-entry",
                user_id="user-1",
                amount=-20,
                entry_type="debit",
                source_type="checkout",
                reference_id="checkout-1",
                created_at=datetime(2026, 1, 3, 0, 0, 0),
            ),
        ],
    )
    session.commit()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/points/ledger/entries",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"entry_type": "credit", "source_type": " Tachigo ", "limit": 10},
    )

    assert response.status_code == 200
    assert response.json() == {
        "entries": [
            {
                "id": "newer-entry",
                "user_id": "user-2",
                "amount": 80,
                "entry_type": "credit",
                "source_type": "tachigo",
                "reference_id": "tachigo:redemption-2",
                "expires_at": None,
                "created_at": "2026-01-02T00:00:00",
            },
            {
                "id": "older-entry",
                "user_id": "user-1",
                "amount": 120,
                "entry_type": "credit",
                "source_type": "tachigo",
                "reference_id": "tachigo:redemption-1",
                "expires_at": None,
                "created_at": "2026-01-01T00:00:00",
            },
        ],
    }


def test_points_ledger_admin_entries_filters_created_range(monkeypatch):
    session = build_session()
    session.add_all(
        [
            PointsLedger(
                id="before-range",
                user_id="user-1",
                amount=120,
                entry_type="credit",
                source_type="tachigo",
                reference_id="tachigo:before",
                created_at=datetime(2026, 1, 1, 23, 59, 59),
            ),
            PointsLedger(
                id="range-start",
                user_id="user-1",
                amount=80,
                entry_type="credit",
                source_type="tachigo",
                reference_id="tachigo:start",
                created_at=datetime(2026, 1, 2, 0, 0, 0),
            ),
            PointsLedger(
                id="range-end",
                user_id="user-2",
                amount=-20,
                entry_type="debit",
                source_type="checkout",
                reference_id="checkout:end",
                created_at=datetime(2026, 1, 3, 0, 0, 0),
            ),
            PointsLedger(
                id="after-range",
                user_id="user-2",
                amount=50,
                entry_type="credit",
                source_type="manual",
                reference_id="manual:after",
                created_at=datetime(2026, 1, 3, 0, 0, 1),
            ),
        ],
    )
    session.commit()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/points/ledger/entries",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={
            "created_from": "2026-01-02T00:00:00",
            "created_to": "2026-01-03T00:00:00",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    assert [entry["id"] for entry in response.json()["entries"]] == [
        "range-end",
        "range-start",
    ]


def test_points_ledger_expired_credits_returns_remaining_exposure(monkeypatch):
    session = build_session()
    session.add_all(
        [
            PointsLedger(
                id="expired-credit",
                user_id="user-1",
                amount=45,
                entry_type="credit",
                source_type="tachigo",
                reference_id="tachigo:expired",
                expires_at=datetime(2000, 1, 1, 0, 0, 0),
                created_at=datetime(1999, 12, 1, 0, 0, 0),
            ),
            PointsLedger(
                id="checkout-debit",
                user_id="user-1",
                amount=-10,
                entry_type="debit",
                source_type="checkout",
                reference_id="checkout-1",
                created_at=datetime(1999, 12, 15, 0, 0, 0),
            ),
        ],
    )
    session.commit()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/points/ledger/expired-credits",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"user_id": "user-1"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "entries": [
            {
                "id": "expired-credit",
                "user_id": "user-1",
                "amount": 45,
                "remaining_amount": 35,
                "source_type": "tachigo",
                "reference_id": "tachigo:expired",
                "expires_at": "2000-01-01T00:00:00",
                "created_at": "1999-12-01T00:00:00",
            },
        ],
    }


def test_points_ledger_admin_entries_rejects_invalid_filter(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/points/ledger/entries",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={"entry_type": "adjust"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "entry_type must be credit or debit"


def test_points_ledger_admin_entries_rejects_invalid_created_range(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.get(
        "/points/ledger/entries",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        params={
            "created_from": "2026-01-03T00:00:00",
            "created_to": "2026-01-02T00:00:00",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid created_at range"


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
