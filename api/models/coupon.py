import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from database import Base


class UserCoupon(Base):
    __tablename__ = "tachiya_demo_coupons"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    coupon_id = Column(String, nullable=False)
    voucher_code = Column(String, unique=True, nullable=False)
    saleor_voucher_id = Column(String)
    idempotency_key = Column(String, unique=True)
    coupon_type = Column(String, nullable=False)
    tcg_cost = Column(Integer, nullable=False)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
