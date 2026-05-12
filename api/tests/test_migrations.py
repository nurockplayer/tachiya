import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ALEMBIC_ROOT = Path(__file__).resolve().parents[1]
HEAD_REVISION = "20260509_0010"
PREVIOUS_REVISION = "20260509_0009"
LATEST_MIGRATION_UNIQUE_NAME = "uq_tachiya_referral_rewards_referee_id"


def make_alembic_config() -> Config:
    config = Config(str(ALEMBIC_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ALEMBIC_ROOT / "migrations"))
    return config


def get_alembic_revision(database_url: str) -> str:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            return connection.exec_driver_sql(
                "select version_num from alembic_version"
            ).scalar_one()
    finally:
        engine.dispose()


def get_index_and_unique_constraint_names(
    database_url: str, table_name: str
) -> set[str]:
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        index_names = {index["name"] for index in inspector.get_indexes(table_name)}
        unique_constraint_names = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints(table_name)
        }
        return index_names | unique_constraint_names
    finally:
        engine.dispose()


def test_alembic_upgrade_head_builds_expected_schema(tmp_path, monkeypatch):
    db_path = tmp_path / "tachiya-migrations.sqlite"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    config = make_alembic_config()

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
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
    finally:
        engine.dispose()


def test_alembic_rollback_smoke_downgrades_one_revision_and_reupgrades_head(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "tachiya-migrations-rollback.sqlite"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    config = make_alembic_config()

    command.upgrade(config, "head")
    assert get_alembic_revision(database_url) == HEAD_REVISION
    assert LATEST_MIGRATION_UNIQUE_NAME in get_index_and_unique_constraint_names(
        database_url, "tachiya_referral_rewards"
    )

    command.downgrade(config, "-1")
    assert get_alembic_revision(database_url) == PREVIOUS_REVISION
    assert LATEST_MIGRATION_UNIQUE_NAME not in get_index_and_unique_constraint_names(
        database_url, "tachiya_referral_rewards"
    )

    command.upgrade(config, "head")
    assert get_alembic_revision(database_url) == HEAD_REVISION
    assert LATEST_MIGRATION_UNIQUE_NAME in get_index_and_unique_constraint_names(
        database_url, "tachiya_referral_rewards"
    )
