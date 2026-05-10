import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint

from database import Base


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class PointsLedger(Base):
    __tablename__ = "tachiya_points_ledger"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "entry_type",
            "reference_id",
            name="uq_tachiya_points_ledger_idempotency",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    entry_type = Column(String, nullable=False, index=True)
    source_type = Column(String, nullable=False, default="manual", server_default="manual", index=True)
    reference_id = Column(String, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
