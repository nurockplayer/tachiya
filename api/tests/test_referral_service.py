import asyncio
import hashlib
import hmac
import json
import sys
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.points_ledger import PointsLedger
from models.referral import ReferralRelationship, ReferralReward
from models.webhook_event import WebhookEvent
from routers import referrals
from services.points_service import PointsService
from services.referral_service import ReferralService


def build_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def add_relationship(session, *, referrer_id="referrer-1", referee_id="referee-1"):
    relationship = ReferralRelationship(
        referrer_id=referrer_id,
        referee_id=referee_id,
    )
    session.add(relationship)
    session.commit()
    return relationship


def test_process_referral_reward_credits_referrer_on_first_purchase():
    session = build_session()
    add_relationship(session)
    service = ReferralService(session, reward_rate=0.05)

    reward = asyncio.run(
        service.process_referral_reward(
            order_id="order-1",
            referee_id="referee-1",
            order_total_amount=1200,
        ),
    )

    assert reward is not None
    assert reward.order_id == "order-1"
    assert reward.referrer_id == "referrer-1"
    assert reward.referee_id == "referee-1"
    assert reward.order_total_amount == 1200
    assert reward.reward_points == 60
    assert reward.ledger_entry_id
    ledger_entry = session.get(PointsLedger, reward.ledger_entry_id)
    assert ledger_entry.source_type == "referral"
    assert ledger_entry.expires_at is None
    assert asyncio.run(PointsService(session).get_balance("referrer-1")) == 60


def test_process_referral_reward_skips_when_referee_has_no_referrer():
    session = build_session()
    service = ReferralService(session, reward_rate=0.05)

    reward = asyncio.run(
        service.process_referral_reward(
            order_id="order-1",
            referee_id="unknown-referee",
            order_total_amount=1200,
        ),
    )

    assert reward is None
    assert session.query(ReferralReward).count() == 0
    assert session.query(PointsLedger).count() == 0


def test_process_referral_reward_is_idempotent_for_same_order():
    session = build_session()
    add_relationship(session)
    service = ReferralService(session, reward_rate=0.05)

    first_reward = asyncio.run(service.process_referral_reward("order-1", "referee-1", 1200))
    second_reward = asyncio.run(service.process_referral_reward("order-1", "referee-1", 1200))

    assert first_reward is not None
    assert second_reward is not None
    assert second_reward.id == first_reward.id
    assert session.query(ReferralReward).count() == 1
    assert session.query(PointsLedger).count() == 1
    assert asyncio.run(PointsService(session).get_balance("referrer-1")) == 60


def test_process_referral_reward_skips_after_referee_first_purchase():
    session = build_session()
    add_relationship(session)
    service = ReferralService(session, reward_rate=0.05)

    first_reward = asyncio.run(service.process_referral_reward("order-1", "referee-1", 1200))
    second_reward = asyncio.run(service.process_referral_reward("order-2", "referee-1", 9999))

    assert first_reward is not None
    assert second_reward is None
    assert session.query(ReferralReward).count() == 1
    assert session.query(PointsLedger).count() == 1
    assert asyncio.run(PointsService(session).get_balance("referrer-1")) == 60


def test_referral_reward_referee_id_is_unique():
    session = build_session()
    session.add_all(
        [
            ReferralReward(
                order_id="order-1",
                referrer_id="referrer-1",
                referee_id="referee-1",
                order_total_amount=1200,
                reward_points=60,
                ledger_entry_id="ledger-1",
            ),
            ReferralReward(
                order_id="order-2",
                referrer_id="referrer-1",
                referee_id="referee-1",
                order_total_amount=9999,
                reward_points=499,
                ledger_entry_id="ledger-2",
            ),
        ],
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_process_referral_reward_rolls_back_ledger_when_reward_commit_fails(monkeypatch):
    session = build_session()
    add_relationship(session)
    service = ReferralService(session, reward_rate=0.05)
    original_commit = session.commit

    def fail_reward_commit():
        if any(isinstance(item, ReferralReward) for item in session.new):
            raise IntegrityError("reward commit failed", {}, RuntimeError("conflict"))
        original_commit()

    monkeypatch.setattr(session, "commit", fail_reward_commit)

    with pytest.raises(IntegrityError):
        asyncio.run(service.process_referral_reward("order-1", "referee-1", 1200))

    session.rollback()
    assert session.query(ReferralReward).count() == 0
    assert session.query(PointsLedger).count() == 0


def test_process_referral_reward_normalizes_identifiers():
    session = build_session()
    add_relationship(session)
    service = ReferralService(session, reward_rate=0.05)

    reward = asyncio.run(
        service.process_referral_reward(
            order_id=" order-1 ",
            referee_id=" referee-1 ",
            order_total_amount=1200,
        ),
    )

    assert reward is not None
    assert reward.order_id == "order-1"
    assert reward.referee_id == "referee-1"
    ledger_entry = session.get(PointsLedger, reward.ledger_entry_id)
    assert ledger_entry.reference_id == "referral:order-1"


@pytest.mark.parametrize(
    ("order_id", "referee_id", "message"),
    [
        (" ", "referee-1", "order_id is required"),
        ("order-1", " ", "referee_id is required"),
    ],
)
def test_process_referral_reward_rejects_blank_identifiers(order_id, referee_id, message):
    session = build_session()
    add_relationship(session)
    service = ReferralService(session, reward_rate=0.05)

    with pytest.raises(ValueError, match=message):
        asyncio.run(
            service.process_referral_reward(
                order_id=order_id,
                referee_id=referee_id,
                order_total_amount=1200,
            ),
        )

    assert session.query(ReferralReward).count() == 0
    assert session.query(PointsLedger).count() == 0


@pytest.mark.parametrize("order_total_amount", [0, -1, True, 1200.5, "1200"])
def test_process_referral_reward_rejects_non_positive_integer_amount(order_total_amount):
    session = build_session()
    add_relationship(session)
    service = ReferralService(session, reward_rate=0.05)

    with pytest.raises(ValueError, match="order_total_amount must be a positive integer"):
        asyncio.run(
            service.process_referral_reward(
                order_id="order-1",
                referee_id="referee-1",
                order_total_amount=order_total_amount,
            ),
        )

    assert session.query(ReferralReward).count() == 0
    assert session.query(PointsLedger).count() == 0


def build_client(session) -> TestClient:
    app = FastAPI()
    app.include_router(referrals.router)

    def override_db():
        yield session

    app.dependency_overrides[referrals.get_db] = override_db
    return TestClient(app)


def signed_order_completed_request(
    client: TestClient,
    *,
    payload: dict,
    event_id: str = "evt-order-1",
    timestamp: int | None = None,
    secret: str = "shared-secret",
):
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = timestamp or int(time.time())
    signed_payload = f"{timestamp}.{event_id}.".encode() + body
    signature = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return client.post(
        "/referrals/webhooks/order-completed",
        headers={
            "Content-Type": "application/json",
            "X-Tachiya-Internal-Secret": secret,
            "X-Tachiya-Webhook-Event-Id": event_id,
            "X-Tachiya-Webhook-Timestamp": str(timestamp),
            "X-Tachiya-Webhook-Signature": signature,
        },
        content=body,
    )


def test_order_completed_webhook_processes_referral_reward(monkeypatch):
    session = build_session()
    add_relationship(session)
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = signed_order_completed_request(
        client,
        payload={
            "order_id": "order-1",
            "referee_id": "referee-1",
            "order_total_amount": 1200,
        },
    )

    assert response.status_code == 200
    assert response.json()["rewarded"] is True
    assert response.json()["reward_points"] == 60
    assert response.json()["ledger_entry_id"]
    event = session.query(WebhookEvent).one()
    assert event.event_id == "evt-order-1"
    assert event.event_type == "referral.order_completed"
    assert asyncio.run(PointsService(session).get_balance("referrer-1")) == 60


def test_order_completed_webhook_rejects_invalid_payload_before_processing(monkeypatch):
    session = build_session()
    add_relationship(session)
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    invalid_payloads = [
        {
            "order_id": "",
            "referee_id": "referee-1",
            "order_total_amount": 1200,
        },
        {
            "order_id": "   ",
            "referee_id": "referee-1",
            "order_total_amount": 1200,
        },
        {
            "order_id": "order-1",
            "referee_id": "",
            "order_total_amount": 1200,
        },
        {
            "order_id": "order-1",
            "referee_id": "   ",
            "order_total_amount": 1200,
        },
        {
            "order_id": "order-1",
            "referee_id": "referee-1",
            "order_total_amount": 0,
        },
    ]

    for index, payload in enumerate(invalid_payloads, start=1):
        response = signed_order_completed_request(
            client,
            payload=payload,
            event_id=f"evt-invalid-{index}",
        )

        assert response.status_code == 422

    assert session.query(WebhookEvent).count() == 0
    assert session.query(ReferralReward).count() == 0
    assert session.query(PointsLedger).count() == 0


def test_order_completed_webhook_rejects_missing_signature_headers(monkeypatch):
    session = build_session()
    add_relationship(session)
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.post(
        "/referrals/webhooks/order-completed",
        headers={"X-Tachiya-Internal-Secret": "shared-secret"},
        json={
            "order_id": "order-1",
            "referee_id": "referee-1",
            "order_total_amount": 1200,
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid webhook signature"
    assert session.query(WebhookEvent).count() == 0
    assert session.query(ReferralReward).count() == 0


def test_order_completed_webhook_rejects_stale_timestamp(monkeypatch):
    session = build_session()
    add_relationship(session)
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = signed_order_completed_request(
        client,
        payload={
            "order_id": "order-1",
            "referee_id": "referee-1",
            "order_total_amount": 1200,
        },
        timestamp=int(time.time()) - 600,
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "stale webhook timestamp"
    assert session.query(WebhookEvent).count() == 0
    assert session.query(ReferralReward).count() == 0


def test_order_completed_webhook_rejects_replayed_event(monkeypatch):
    session = build_session()
    add_relationship(session)
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    payload = {
        "order_id": "order-1",
        "referee_id": "referee-1",
        "order_total_amount": 1200,
    }

    first_response = signed_order_completed_request(client, payload=payload)
    second_response = signed_order_completed_request(client, payload=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "webhook event already processed"
    assert session.query(WebhookEvent).count() == 1
    assert session.query(ReferralReward).count() == 1
    assert session.query(PointsLedger).count() == 1


def test_order_completed_webhook_rejects_missing_internal_secret(monkeypatch):
    session = build_session()
    client = build_client(session)
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")

    response = client.post(
        "/referrals/webhooks/order-completed",
        json={
            "order_id": "order-1",
            "referee_id": "referee-1",
            "order_total_amount": 1200,
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid internal secret"
