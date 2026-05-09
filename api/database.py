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
    ensure_coupon_idempotency_key_column(engine)


def ensure_coupon_idempotency_key_column(bind=engine):
    inspector = inspect(bind)
    if "tachiya_demo_coupons" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("tachiya_demo_coupons")}
    if "idempotency_key" not in columns:
        with bind.begin() as conn:
            conn.execute(
                text("ALTER TABLE tachiya_demo_coupons ADD COLUMN idempotency_key VARCHAR")
            )

    indexes = {index["name"] for index in inspector.get_indexes("tachiya_demo_coupons")}
    if "ix_tachiya_demo_coupons_idempotency_key" in indexes:
        return

    with bind.begin() as conn:
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ix_tachiya_demo_coupons_idempotency_key "
                "ON tachiya_demo_coupons (idempotency_key)"
            )
        )
