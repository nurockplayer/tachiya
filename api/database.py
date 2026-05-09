import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://saleor:saleor@localhost:5432/saleor")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_ready(bind=engine) -> bool:
    with bind.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True


def create_tables():
    import_models()
    Base.metadata.create_all(bind=engine)
    ensure_coupon_extension_columns(engine)
    ensure_points_ledger_extension_columns(engine)


def import_models():
    from models import (  # noqa: F401
        coupon,
        coupon_redemption_audit,
        identity_audit_event,
        identity_mapping,
        points_ledger,
        referral,
        webhook_event,
    )


def ensure_coupon_extension_columns(bind=engine):
    inspector = inspect(bind)
    if "tachiya_demo_coupons" not in inspector.get_table_names():
        return

    _ensure_column(
        bind,
        inspector,
        table_name="tachiya_demo_coupons",
        column_name="idempotency_key",
        column_definition="idempotency_key VARCHAR",
        index_name="ix_tachiya_demo_coupons_idempotency_key",
        unique=True,
    )
    _ensure_column(
        bind,
        inspector,
        table_name="tachiya_demo_coupons",
        column_name="redemption_token",
        column_definition="redemption_token VARCHAR",
        index_name="ix_tachiya_demo_coupons_redemption_token",
        unique=True,
    )


def ensure_coupon_idempotency_key_column(bind=engine):
    ensure_coupon_extension_columns(bind)


def ensure_points_ledger_extension_columns(bind=engine):
    inspector = inspect(bind)
    if "tachiya_points_ledger" not in inspector.get_table_names():
        return

    _ensure_column(
        bind,
        inspector,
        table_name="tachiya_points_ledger",
        column_name="source_type",
        column_definition="source_type VARCHAR NOT NULL DEFAULT 'manual'",
        index_name="ix_tachiya_points_ledger_source_type",
    )
    _ensure_column(
        bind,
        inspector,
        table_name="tachiya_points_ledger",
        column_name="expires_at",
        column_definition="expires_at TIMESTAMP",
    )
    _ensure_index(
        bind,
        inspector,
        table_name="tachiya_points_ledger",
        index_name="uq_tachiya_points_ledger_idempotency",
        columns=["user_id", "entry_type", "reference_id"],
        unique=True,
    )


def _ensure_column(
    bind,
    inspector,
    *,
    table_name: str,
    column_name: str,
    column_definition: str,
    index_name: str | None = None,
    unique: bool = False,
):
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name not in columns:
        with bind.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_definition}"))
        inspector = inspect(bind)

    if index_name is None:
        return

    _ensure_index(
        bind,
        inspector,
        table_name=table_name,
        index_name=index_name,
        columns=[column_name],
        unique=unique,
    )


def _ensure_index(
    bind,
    inspector,
    *,
    table_name: str,
    index_name: str,
    columns: list[str],
    unique: bool = False,
):
    indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    unique_constraints = {
        constraint["name"] for constraint in inspector.get_unique_constraints(table_name)
    }
    if index_name in indexes or index_name in unique_constraints:
        return

    unique_sql = "UNIQUE " if unique else ""
    column_sql = ", ".join(columns)
    with bind.begin() as conn:
        conn.execute(
            text(
                f"CREATE {unique_sql}INDEX IF NOT EXISTS "
                f"{index_name} "
                f"ON {table_name} ({column_sql})"
            )
        )
