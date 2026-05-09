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


def create_tables():
    Base.metadata.create_all(bind=engine)
    ensure_coupon_extension_columns(engine)


def ensure_coupon_extension_columns(bind=engine):
    inspector = inspect(bind)
    if "tachiya_demo_coupons" not in inspector.get_table_names():
        return

    _ensure_column(
        bind,
        inspector,
        column_name="idempotency_key",
        index_name="ix_tachiya_demo_coupons_idempotency_key",
    )
    _ensure_column(
        bind,
        inspector,
        column_name="redemption_token",
        index_name="ix_tachiya_demo_coupons_redemption_token",
    )


def ensure_coupon_idempotency_key_column(bind=engine):
    ensure_coupon_extension_columns(bind)


def _ensure_column(bind, inspector, *, column_name: str, index_name: str):
    columns = {column["name"] for column in inspector.get_columns("tachiya_demo_coupons")}
    if column_name not in columns:
        with bind.begin() as conn:
            conn.execute(text(f"ALTER TABLE tachiya_demo_coupons ADD COLUMN {column_name} VARCHAR"))
        inspector = inspect(bind)

    indexes = {index["name"] for index in inspector.get_indexes("tachiya_demo_coupons")}
    if index_name in indexes:
        return

    with bind.begin() as conn:
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                f"{index_name} "
                f"ON tachiya_demo_coupons ({column_name})"
            )
        )
