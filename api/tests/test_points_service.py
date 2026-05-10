import asyncio
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from conftest import build_sqlite_session
from models.points_ledger import PointsLedger
from services.points_service import PointsService


def build_session():
    return build_sqlite_session()


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


def test_get_balance_normalizes_user_id():
    session = build_session()
    service = PointsService(session)
    asyncio.run(service.credit(user_id="user-1", amount=120, reference_id="order-1"))

    assert asyncio.run(service.get_balance(" user-1 ")) == 120


def test_get_balance_rejects_blank_user_id():
    session = build_session()
    service = PointsService(session)

    with pytest.raises(ValueError, match="user_id is required"):
        asyncio.run(service.get_balance("   "))


def test_get_balance_excludes_expired_unspent_credits():
    session = build_session()
    service = PointsService(session)
    session.add_all(
        [
            PointsLedger(
                id="expired-credit",
                user_id="user-1",
                amount=120,
                entry_type="credit",
                source_type="tachigo",
                reference_id="tachigo:expired",
                expires_at=datetime(2026, 1, 10, 0, 0, 0),
                created_at=datetime(2026, 1, 1, 0, 0, 0),
            ),
            PointsLedger(
                id="active-credit",
                user_id="user-1",
                amount=40,
                entry_type="credit",
                source_type="manual",
                reference_id="manual:active",
                expires_at=datetime(2026, 12, 31, 23, 59, 59),
                created_at=datetime(2026, 1, 2, 0, 0, 0),
            ),
        ],
    )
    session.commit()

    assert asyncio.run(service.get_balance("user-1", at=datetime(2026, 6, 1, 0, 0, 0))) == 40


def test_get_balance_does_not_double_expire_spent_credits():
    session = build_session()
    service = PointsService(session)
    session.add_all(
        [
            PointsLedger(
                id="expiring-credit",
                user_id="user-1",
                amount=100,
                entry_type="credit",
                source_type="tachigo",
                reference_id="tachigo:redemption-1",
                expires_at=datetime(2026, 1, 10, 0, 0, 0),
                created_at=datetime(2026, 1, 1, 0, 0, 0),
            ),
            PointsLedger(
                id="permanent-credit",
                user_id="user-1",
                amount=50,
                entry_type="credit",
                source_type="manual",
                reference_id="manual:adjustment-1",
                created_at=datetime(2026, 1, 2, 0, 0, 0),
            ),
            PointsLedger(
                id="checkout-debit",
                user_id="user-1",
                amount=-30,
                entry_type="debit",
                source_type="checkout",
                reference_id="checkout-1",
                created_at=datetime(2026, 1, 3, 0, 0, 0),
            ),
        ],
    )
    session.commit()

    assert asyncio.run(service.get_balance("user-1", at=datetime(2026, 1, 11, 0, 0, 0))) == 50


def test_debit_rejects_expired_credit_balance():
    session = build_session()
    service = PointsService(session)
    asyncio.run(
        service.credit(
            user_id="user-1",
            amount=120,
            reference_id="tachigo:expired",
            source_type="tachigo",
            expires_at=datetime(2000, 1, 1, 0, 0, 0),
        ),
    )

    with pytest.raises(ValueError, match="insufficient balance"):
        asyncio.run(service.debit(user_id="user-1", amount=1, reference_id="checkout-1"))

    assert session.query(PointsLedger).count() == 1


def test_list_expired_credit_exposures_returns_unspent_expired_credit_amounts():
    session = build_session()
    service = PointsService(session)
    session.add_all(
        [
            PointsLedger(
                id="expired-credit",
                user_id="user-1",
                amount=100,
                entry_type="credit",
                source_type="tachigo",
                reference_id="tachigo:redemption-1",
                expires_at=datetime(2026, 1, 10, 0, 0, 0),
                created_at=datetime(2026, 1, 1, 0, 0, 0),
            ),
            PointsLedger(
                id="active-credit",
                user_id="user-1",
                amount=50,
                entry_type="credit",
                source_type="manual",
                reference_id="manual:adjustment-1",
                created_at=datetime(2026, 1, 2, 0, 0, 0),
            ),
            PointsLedger(
                id="checkout-debit",
                user_id="user-1",
                amount=-30,
                entry_type="debit",
                source_type="checkout",
                reference_id="checkout-1",
                created_at=datetime(2026, 1, 3, 0, 0, 0),
            ),
        ],
    )
    session.commit()

    exposures = service.list_expired_credit_exposures(
        "user-1",
        at=datetime(2026, 1, 11, 0, 0, 0),
    )

    assert len(exposures) == 1
    assert exposures[0].entry.id == "expired-credit"
    assert exposures[0].remaining_amount == 70


def test_list_expired_credit_exposures_rejects_invalid_limit():
    session = build_session()
    service = PointsService(session)

    with pytest.raises(ValueError, match="limit must be between 1 and 100"):
        service.list_expired_credit_exposures("user-1", limit=-1)


def test_list_entries_returns_requested_user_newest_first():
    session = build_session()
    service = PointsService(session)
    session.add_all(
        [
            PointsLedger(
                id="old-entry",
                user_id="user-1",
                amount=120,
                entry_type="credit",
                source_type="tachigo",
                reference_id="tachigo:redemption-1",
                created_at=datetime(2026, 1, 1, 0, 0, 0),
            ),
            PointsLedger(
                id="other-user-entry",
                user_id="user-2",
                amount=999,
                entry_type="credit",
                source_type="manual",
                reference_id="order-2",
                created_at=datetime(2026, 1, 3, 0, 0, 0),
            ),
            PointsLedger(
                id="new-entry",
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

    entries = asyncio.run(service.list_entries("user-1", limit=10))

    assert [entry.id for entry in entries] == ["new-entry", "old-entry"]
    assert entries[0].amount == -20
    assert entries[0].source_type == "checkout"
    assert entries[0].reference_id == "checkout-1"
    assert entries[0].expires_at == datetime(2026, 12, 31, 23, 59, 59)


def test_list_entries_normalizes_user_id():
    session = build_session()
    service = PointsService(session)
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

    entries = asyncio.run(service.list_entries(" user-1 ", limit=10))

    assert [entry.id for entry in entries] == ["entry-1"]


def test_list_entries_rejects_blank_user_id():
    session = build_session()
    service = PointsService(session)

    with pytest.raises(ValueError, match="user_id is required"):
        asyncio.run(service.list_entries("   "))


def test_list_entries_rejects_invalid_limit():
    session = build_session()
    service = PointsService(session)

    with pytest.raises(ValueError, match="limit must be between 1 and 100"):
        asyncio.run(service.list_entries("user-1", limit=0))


def test_list_admin_entries_filters_and_returns_newest_first():
    session = build_session()
    service = PointsService(session)
    session.add_all(
        [
            PointsLedger(
                id="older-tachigo-entry",
                user_id="user-1",
                amount=120,
                entry_type="credit",
                source_type="tachigo",
                reference_id="tachigo:redemption-1",
                created_at=datetime(2026, 1, 1, 0, 0, 0),
            ),
            PointsLedger(
                id="newer-tachigo-entry",
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

    tachigo_credits = service.list_admin_entries(
        entry_type=" credit ",
        source_type=" Tachigo ",
        limit=10,
    )
    user_entries = service.list_admin_entries(user_id=" user-1 ", limit=10)
    reference_entries = service.list_admin_entries(reference_id=" checkout-1 ", limit=10)

    assert [entry.id for entry in tachigo_credits] == [
        "newer-tachigo-entry",
        "older-tachigo-entry",
    ]
    assert [entry.id for entry in user_entries] == [
        "checkout-entry",
        "older-tachigo-entry",
    ]
    assert [entry.id for entry in reference_entries] == ["checkout-entry"]


def test_list_admin_entries_filters_created_range_inclusively():
    session = build_session()
    service = PointsService(session)
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

    entries = service.list_admin_entries(
        created_from=datetime(2026, 1, 2, 0, 0, 0),
        created_to=datetime(2026, 1, 3, 0, 0, 0),
        limit=10,
    )

    assert [entry.id for entry in entries] == ["range-end", "range-start"]


def test_list_admin_entries_rejects_invalid_created_range():
    session = build_session()
    service = PointsService(session)

    with pytest.raises(ValueError, match="invalid created_at range"):
        service.list_admin_entries(
            created_from=datetime(2026, 1, 3, 0, 0, 0),
            created_to=datetime(2026, 1, 2, 0, 0, 0),
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"user_id": " "}, "user_id is required"),
        ({"entry_type": "adjust"}, "entry_type must be credit or debit"),
        ({"source_type": " "}, "source_type is required"),
        ({"reference_id": " "}, "reference_id is required"),
    ],
)
def test_list_admin_entries_rejects_invalid_filters(kwargs, message):
    session = build_session()
    service = PointsService(session)

    with pytest.raises(ValueError, match=message):
        service.list_admin_entries(**kwargs)


def test_list_admin_entries_rejects_invalid_limit():
    session = build_session()
    service = PointsService(session)

    with pytest.raises(ValueError, match="limit must be between 1 and 100"):
        service.list_admin_entries(limit=101)


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


@pytest.mark.parametrize("method", ["credit", "debit"])
def test_credit_and_debit_reject_blank_user_id(method):
    session = build_session()
    service = PointsService(session)

    with pytest.raises(ValueError, match="user_id is required"):
        asyncio.run(getattr(service, method)(" ", 10, "order-1"))

    assert session.query(PointsLedger).count() == 0


@pytest.mark.parametrize("method", ["credit", "debit"])
def test_credit_and_debit_reject_blank_reference_id(method):
    session = build_session()
    service = PointsService(session)
    if method == "debit":
        asyncio.run(service.credit("user-1", 20, "seed-credit"))

    with pytest.raises(ValueError, match="reference_id is required"):
        asyncio.run(getattr(service, method)("user-1", 10, " "))

    expected_entries = 1 if method == "debit" else 0
    assert session.query(PointsLedger).count() == expected_entries
