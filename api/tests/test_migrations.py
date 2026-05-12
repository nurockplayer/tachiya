import os
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
MIGRATION_SMOKE_OPT_IN_ENV = "TACHIYA_MIGRATION_SMOKE_USE_DATABASE_URL"


def make_alembic_config() -> Config:
    config = Config(str(ALEMBIC_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ALEMBIC_ROOT / "migrations"))
    return config


def migration_database_url(tmp_path, monkeypatch, filename: str) -> str:
    database_url = os.environ.get("DATABASE_URL")
    if database_url and os.environ.get(MIGRATION_SMOKE_OPT_IN_ENV) == "1":
        return database_url

    db_path = tmp_path / filename
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    return database_url


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


def has_table(database_url: str, table_name: str) -> bool:
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        return table_name in inspector.get_table_names()
    finally:
        engine.dispose()


def downgrade_to_base_if_initialized(config: Config, database_url: str) -> None:
    if has_table(database_url, "alembic_version"):
        command.downgrade(config, "base")


def test_migration_database_url_uses_existing_database_url_with_explicit_opt_in(
    tmp_path, monkeypatch
):
    existing_database_url = "postgresql://tachiya:tachiya@localhost:5432/tachiya"
    monkeypatch.setenv("DATABASE_URL", existing_database_url)
    monkeypatch.setenv(MIGRATION_SMOKE_OPT_IN_ENV, "1")

    assert (
        migration_database_url(tmp_path, monkeypatch, "ignored.sqlite")
        == existing_database_url
    )


def test_migration_database_url_falls_back_to_temp_sqlite_when_opt_in_missing(
    tmp_path, monkeypatch
):
    existing_database_url = "postgresql://tachiya:tachiya@localhost:5432/tachiya"
    monkeypatch.setenv("DATABASE_URL", existing_database_url)
    monkeypatch.delenv(MIGRATION_SMOKE_OPT_IN_ENV, raising=False)

    database_url = migration_database_url(
        tmp_path, monkeypatch, "tachiya-migrations.sqlite"
    )

    assert database_url == f"sqlite:///{tmp_path / 'tachiya-migrations.sqlite'}"
    assert os.environ["DATABASE_URL"] == database_url


def test_migration_database_url_falls_back_to_temp_sqlite(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv(MIGRATION_SMOKE_OPT_IN_ENV, raising=False)

    database_url = migration_database_url(
        tmp_path, monkeypatch, "tachiya-migrations.sqlite"
    )

    assert database_url == f"sqlite:///{tmp_path / 'tachiya-migrations.sqlite'}"
    assert os.environ["DATABASE_URL"] == database_url


def test_alembic_upgrade_head_builds_expected_schema(tmp_path, monkeypatch):
    database_url = migration_database_url(
        tmp_path, monkeypatch, "tachiya-migrations.sqlite"
    )
    config = make_alembic_config()
    downgrade_to_base_if_initialized(config, database_url)

    try:
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
                index["name"]
                for index in inspector.get_indexes("tachiya_points_ledger")
            }
            points_unique_constraints = {
                constraint["name"]
                for constraint in inspector.get_unique_constraints(
                    "tachiya_points_ledger"
                )
            }
            assert "uq_tachiya_points_ledger_idempotency" in (
                points_indexes | points_unique_constraints
            )
        finally:
            engine.dispose()
    finally:
        downgrade_to_base_if_initialized(config, database_url)


def test_alembic_rollback_smoke_downgrades_one_revision_and_reupgrades_head(
    tmp_path, monkeypatch
):
    database_url = migration_database_url(
        tmp_path, monkeypatch, "tachiya-migrations-rollback.sqlite"
    )
    config = make_alembic_config()
    downgrade_to_base_if_initialized(config, database_url)

    try:
        command.upgrade(config, "head")
        assert get_alembic_revision(database_url) == HEAD_REVISION
        assert LATEST_MIGRATION_UNIQUE_NAME in get_index_and_unique_constraint_names(
            database_url, "tachiya_referral_rewards"
        )

        command.downgrade(config, "-1")
        assert get_alembic_revision(database_url) == PREVIOUS_REVISION
        assert (
            LATEST_MIGRATION_UNIQUE_NAME
            not in get_index_and_unique_constraint_names(
                database_url, "tachiya_referral_rewards"
            )
        )

        command.upgrade(config, "head")
        assert get_alembic_revision(database_url) == HEAD_REVISION
        assert LATEST_MIGRATION_UNIQUE_NAME in get_index_and_unique_constraint_names(
            database_url, "tachiya_referral_rewards"
        )
    finally:
        downgrade_to_base_if_initialized(config, database_url)
