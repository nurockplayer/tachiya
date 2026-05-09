import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import ensure_coupon_idempotency_key_column


def test_ensure_coupon_idempotency_key_column_adds_missing_column():
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

    ensure_coupon_idempotency_key_column(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("tachiya_demo_coupons")}
    assert "idempotency_key" in columns
