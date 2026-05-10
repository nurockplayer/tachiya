import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String

from database import Base


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class UserCoupon(Base):
    __tablename__ = "tachiya_demo_coupons"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    coupon_id = Column(String, nullable=False, index=True)
    voucher_code = Column(String, unique=True, nullable=False)
    saleor_voucher_id = Column(String)
    idempotency_key = Column(String, unique=True)
    redemption_token = Column(String, unique=True, default=lambda: str(uuid.uuid4()))
    coupon_type = Column(String, nullable=False)
    tcg_cost = Column(Integer, nullable=False)
    status = Column(String, default="active", index=True)
    created_at = Column(DateTime, default=utcnow, index=True)
