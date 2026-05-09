import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String

from database import Base


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class PointsLedger(Base):
    __tablename__ = "tachiya_points_ledger"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    entry_type = Column(String, nullable=False)
    reference_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
