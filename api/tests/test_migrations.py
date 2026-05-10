import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_alembic_upgrade_head_builds_expected_schema(tmp_path, monkeypatch):
    db_path = tmp_path / "tachiya-migrations.sqlite"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[1] / "migrations")
    )

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert {
        "tachiya_demo_coupons",
        "tachiya_coupon_redemption_audit_events",
        "tachiya_identity_mappings",
        "tachiya_points_ledger",
        "tachiya_referral_relationships",
        "tachiya_referral_rewards",
        "tachiya_streamer_profiles",
        "tachiya_streamer_product_assignments",
        "tachiya_streamer_revenue_share_records",
        "tachiya_webhook_events",
    }.issubset(set(inspector.get_table_names()))

    points_indexes = {
        index["name"] for index in inspector.get_indexes("tachiya_points_ledger")
    }
    points_unique_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("tachiya_points_ledger")
    }
    assert "uq_tachiya_points_ledger_idempotency" in (
        points_indexes | points_unique_constraints
    )
