import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, String

from database import Base


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class CouponRedemptionAuditEvent(Base):
    __tablename__ = "tachiya_coupon_redemption_audit_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    coupon_id = Column(String, nullable=False, index=True)
    idempotency_key = Column(String, nullable=True, index=True)
    redemption_token = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, index=True)
    reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
