import asyncio
import sys
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.points_ledger import PointsLedger
from services.points_service import PointsService


def build_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_credit_writes_ledger_entry_and_updates_balance():
    session = build_session()
    service = PointsService(session)

    entry = asyncio.run(
        service.credit(user_id="user-1", amount=120, reference_id="order-1"),
    )

    assert entry.user_id == "user-1"
    assert entry.amount == 120
    assert entry.entry_type == "credit"
    assert entry.reference_id == "order-1"
    assert asyncio.run(service.get_balance("user-1")) == 120


def test_credit_writes_source_type_and_expiration_metadata():
    session = build_session()
    service = PointsService(session)
    expires_at = datetime(2026, 12, 31, 23, 59, 59)

    entry = asyncio.run(
        service.credit(
            user_id="user-1",
            amount=120,
            reference_id="tachigo:redemption-1",
            source_type="tachigo",
            expires_at=expires_at,
        ),
    )

    assert entry.source_type == "tachigo"
    assert entry.expires_at == expires_at


def test_credit_is_idempotent_for_same_user_entry_type_and_reference():
    session = build_session()
    service = PointsService(session)

    first_entry = asyncio.run(
        service.credit(
            user_id="user-1",
            amount=120,
            reference_id="tachigo:redemption-1",
            source_type="tachigo",
        ),
    )
    second_entry = asyncio.run(
        service.credit(
            user_id="user-1",
            amount=120,
            reference_id="tachigo:redemption-1",
            source_type="tachigo",
        ),
    )

    assert second_entry.id == first_entry.id
    assert session.query(PointsLedger).count() == 1
    assert asyncio.run(service.get_balance("user-1")) == 120


def test_credit_idempotency_allows_same_reference_for_different_users():
    session = build_session()
    service = PointsService(session)

    first_entry = asyncio.run(service.credit("user-1", 120, "tachigo:redemption-1"))
    second_entry = asyncio.run(service.credit("user-2", 120, "tachigo:redemption-1"))

    assert second_entry.id != first_entry.id
    assert session.query(PointsLedger).count() == 2
    assert asyncio.run(service.get_balance("user-1")) == 120
    assert asyncio.run(service.get_balance("user-2")) == 120


def test_credit_rejects_idempotency_key_conflict():
    session = build_session()
    service = PointsService(session)
    asyncio.run(service.credit("user-1", 120, "tachigo:redemption-1", source_type="tachigo"))

    with pytest.raises(ValueError, match="idempotency key conflict"):
        asyncio.run(
            service.credit(
                "user-1",
                999,
                "tachigo:redemption-1",
                source_type="tachigo",
            ),
        )

    assert session.query(PointsLedger).count() == 1
    assert asyncio.run(service.get_balance("user-1")) == 120


def test_debit_writes_negative_ledger_entry_and_updates_balance():
    session = build_session()
    service = PointsService(session)
    asyncio.run(service.credit(user_id="user-1", amount=120, reference_id="order-1"))

    entry = asyncio.run(
        service.debit(user_id="user-1", amount=45, reference_id="checkout-1"),
    )

    assert entry.user_id == "user-1"
    assert entry.amount == -45
    assert entry.entry_type == "debit"
    assert entry.reference_id == "checkout-1"
    assert entry.source_type == "manual"
    assert entry.expires_at is None
    assert asyncio.run(service.get_balance("user-1")) == 75


def test_debit_is_idempotent_before_balance_check():
    session = build_session()
    service = PointsService(session)
    asyncio.run(service.credit(user_id="user-1", amount=120, reference_id="order-1"))

    first_entry = asyncio.run(service.debit("user-1", 100, "checkout-1"))
    second_entry = asyncio.run(service.debit("user-1", 100, "checkout-1"))

    assert second_entry.id == first_entry.id
    assert session.query(PointsLedger).count() == 2
    assert asyncio.run(service.get_balance("user-1")) == 20


def test_get_balance_only_sums_requested_user():
    session = build_session()
    service = PointsService(session)
    asyncio.run(service.credit(user_id="user-1", amount=120, reference_id="order-1"))
    asyncio.run(service.credit(user_id="user-2", amount=999, reference_id="order-2"))
    asyncio.run(service.debit(user_id="user-1", amount=20, reference_id="checkout-1"))

    assert asyncio.run(service.get_balance("user-1")) == 100
    assert asyncio.run(service.get_balance("user-2")) == 999


@pytest.mark.parametrize("method", ["credit", "debit"])
def test_credit_and_debit_reject_non_positive_amounts(method):
    session = build_session()
    service = PointsService(session)

    with pytest.raises(ValueError, match="amount must be positive"):
        asyncio.run(getattr(service, method)("user-1", 0, "bad-reference"))

    assert session.query(PointsLedger).count() == 0


def test_debit_rejects_insufficient_balance():
    session = build_session()
    service = PointsService(session)
    asyncio.run(service.credit(user_id="user-1", amount=30, reference_id="order-1"))

    with pytest.raises(ValueError, match="insufficient balance"):
        asyncio.run(service.debit(user_id="user-1", amount=31, reference_id="checkout-1"))

    assert asyncio.run(service.get_balance("user-1")) == 30


def test_credit_rejects_blank_source_type():
    session = build_session()
    service = PointsService(session)

    with pytest.raises(ValueError, match="source_type is required"):
        asyncio.run(service.credit("user-1", 10, "order-1", source_type=" "))

    assert session.query(PointsLedger).count() == 0
