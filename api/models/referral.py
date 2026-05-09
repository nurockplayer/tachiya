import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String

from database import Base


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class ReferralRelationship(Base):
    __tablename__ = "tachiya_referral_relationships"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    referrer_id = Column(String, nullable=False, index=True)
    referee_id = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class ReferralReward(Base):
    __tablename__ = "tachiya_referral_rewards"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String, nullable=False, unique=True, index=True)
    referrer_id = Column(String, nullable=False, index=True)
    referee_id = Column(String, nullable=False, index=True)
    order_total_amount = Column(Integer, nullable=False)
    reward_points = Column(Integer, nullable=False)
    ledger_entry_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
