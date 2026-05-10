import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import (
    Base,
    ensure_coupon_extension_columns,
    ensure_points_ledger_extension_columns,
    import_models,
)


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
    indexes = {index["name"] for index in inspect(engine).get_indexes("tachiya_demo_coupons")}
    assert "idempotency_key" in columns
    assert "redemption_token" in columns
    assert "ix_tachiya_demo_coupons_coupon_id" in indexes
    assert "ix_tachiya_demo_coupons_status" in indexes
    assert "ix_tachiya_demo_coupons_created_at" in indexes


def test_metadata_includes_coupon_admin_lookup_indexes():
    engine = create_engine("sqlite:///:memory:")
    import_models()

    Base.metadata.create_all(bind=engine)

    indexes = {
        index["name"]: index
        for index in inspect(engine).get_indexes("tachiya_demo_coupons")
    }

    assert "ix_tachiya_demo_coupons_coupon_id" in indexes
    assert "ix_tachiya_demo_coupons_status" in indexes
    assert "ix_tachiya_demo_coupons_created_at" in indexes


def test_metadata_includes_identity_mapping_lookup_indexes():
    engine = create_engine("sqlite:///:memory:")
    import_models()

    Base.metadata.create_all(bind=engine)

    indexes = {
        index["name"]: index
        for index in inspect(engine).get_indexes("tachiya_identity_mappings")
    }

    assert "ix_tachiya_identity_mappings_saleor_customer_id" in indexes
    assert "ix_tachiya_identity_mappings_provider" in indexes
    assert "ix_tachiya_identity_mappings_external_subject" in indexes
    assert "ix_tachiya_identity_mappings_created_at" in indexes


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


def test_metadata_includes_streamer_profiles_table():
    engine = create_engine("sqlite:///:memory:")
    import_models()

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    columns = {
        column["name"]
        for column in inspector.get_columns("tachiya_streamer_profiles")
    }
    indexes = {
        index["name"]: index
        for index in inspector.get_indexes("tachiya_streamer_profiles")
    }

    assert {
        "id",
        "slug",
        "display_name",
        "saleor_collection_id",
        "commission_bps",
        "active",
        "created_at",
        "updated_at",
    }.issubset(columns)
    assert "ix_tachiya_streamer_profiles_slug" in indexes
    assert "ix_tachiya_streamer_profiles_saleor_collection_id" in indexes
    assert "ix_tachiya_streamer_profiles_created_at" in indexes
    assert indexes["ix_tachiya_streamer_profiles_slug"]["unique"] == 1
    assert indexes["ix_tachiya_streamer_profiles_saleor_collection_id"]["unique"] == 1


def test_metadata_includes_streamer_product_assignments_table():
    engine = create_engine("sqlite:///:memory:")
    import_models()

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    columns = {
        column["name"]
        for column in inspector.get_columns("tachiya_streamer_product_assignments")
    }
    indexes = {
        index["name"]: index
        for index in inspector.get_indexes("tachiya_streamer_product_assignments")
    }
    foreign_keys = inspector.get_foreign_keys("tachiya_streamer_product_assignments")

    assert {
        "id",
        "saleor_product_id",
        "streamer_profile_id",
        "streamer_slug",
        "source",
        "created_at",
        "updated_at",
    }.issubset(columns)
    assert "ix_tachiya_streamer_product_assignments_saleor_product_id" in indexes
    assert "ix_tachiya_streamer_product_assignments_streamer_profile_id" in indexes
    assert "ix_tachiya_streamer_product_assignments_streamer_slug" in indexes
    assert "ix_tachiya_streamer_product_assignments_created_at" in indexes
    assert indexes["ix_tachiya_streamer_product_assignments_saleor_product_id"]["unique"] == 1
    assert foreign_keys[0]["referred_table"] == "tachiya_streamer_profiles"


def test_metadata_includes_streamer_revenue_share_records_table():
    engine = create_engine("sqlite:///:memory:")
    import_models()

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    columns = {
        column["name"]
        for column in inspector.get_columns("tachiya_streamer_revenue_share_records")
    }
    indexes = {
        index["name"]: index
        for index in inspector.get_indexes("tachiya_streamer_revenue_share_records")
    }
    unique_constraints = {
        constraint["name"]: constraint
        for constraint in inspector.get_unique_constraints(
            "tachiya_streamer_revenue_share_records",
        )
    }
    foreign_keys = inspector.get_foreign_keys("tachiya_streamer_revenue_share_records")

    assert {
        "id",
        "order_id",
        "streamer_profile_id",
        "streamer_slug",
        "gross_amount",
        "commission_bps",
        "share_amount",
        "status",
        "created_at",
        "updated_at",
    }.issubset(columns)
    assert "ix_tachiya_streamer_revenue_share_records_order_id" in indexes
    assert "ix_tachiya_streamer_revenue_share_records_status" in indexes
    assert "ix_tachiya_streamer_revenue_share_records_streamer_profile_id" in indexes
    assert "ix_tachiya_streamer_revenue_share_records_streamer_slug" in indexes
    assert "ix_tachiya_streamer_revenue_share_records_created_at" in indexes
    assert (
        unique_constraints["uq_tachiya_streamer_revenue_share_order_streamer"]["column_names"]
        == ["order_id", "streamer_slug"]
    )
    assert foreign_keys[0]["referred_table"] == "tachiya_streamer_profiles"
