import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import ensure_coupon_extension_columns, ensure_points_ledger_extension_columns


def test_ensure_coupon_extension_columns_adds_missing_columns():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE tachiya_demo_coupons (
                    id VARCHAR PRIMARY KEY,
                    coupon_id VARCHAR NOT NULL,
                    voucher_code VARCHAR NOT NULL UNIQUE,
                    saleor_voucher_id VARCHAR,
                    coupon_type VARCHAR NOT NULL,
                    tcg_cost INTEGER NOT NULL,
                    status VARCHAR,
                    created_at TIMESTAMP
                )
                """
            )
        )

    ensure_coupon_extension_columns(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("tachiya_demo_coupons")}
    assert "idempotency_key" in columns
    assert "redemption_token" in columns


def test_ensure_points_ledger_extension_columns_backfills_missing_columns():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE tachiya_points_ledger (
                    id VARCHAR PRIMARY KEY,
                    user_id VARCHAR NOT NULL,
                    amount INTEGER NOT NULL,
                    entry_type VARCHAR NOT NULL,
                    reference_id VARCHAR NOT NULL,
                    created_at TIMESTAMP NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO tachiya_points_ledger (
                    id,
                    user_id,
                    amount,
                    entry_type,
                    reference_id,
                    created_at
                ) VALUES (
                    'ledger-1',
                    'user-1',
                    100,
                    'credit',
                    'order-1',
                    '2026-01-01 00:00:00'
                )
                """
            )
        )

    ensure_points_ledger_extension_columns(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("tachiya_points_ledger")}
    assert "source_type" in columns
    assert "expires_at" in columns
    indexes = {index["name"] for index in inspect(engine).get_indexes("tachiya_points_ledger")}
    assert "ix_tachiya_points_ledger_source_type" in indexes
    assert "uq_tachiya_points_ledger_idempotency" in indexes

    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT source_type, expires_at
                FROM tachiya_points_ledger
                WHERE id = 'ledger-1'
                """
            )
        ).one()

    assert row.source_type == "manual"
    assert row.expires_at is None
