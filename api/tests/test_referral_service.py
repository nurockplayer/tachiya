import asyncio
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.points_ledger import PointsLedger
from models.referral import ReferralRelationship, ReferralReward
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


def build_client(session) -> TestClient:
    app = FastAPI()
    app.include_router(referrals.router)

    def override_db():
        yield session

    app.dependency_overrides[referrals.get_db] = override_db
    return TestClient(app)


def test_order_completed_webhook_processes_referral_reward(monkeypatch):
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

    assert response.status_code == 200
    assert response.json()["rewarded"] is True
    assert response.json()["reward_points"] == 60
    assert response.json()["ledger_entry_id"]
    assert asyncio.run(PointsService(session).get_balance("referrer-1")) == 60


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
