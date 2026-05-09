import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from database import Base


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class StreamerProfile(Base):
    __tablename__ = "tachiya_streamer_profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    slug = Column(String, nullable=False, unique=True, index=True)
    display_name = Column(String, nullable=False)
    saleor_collection_id = Column(String, nullable=True, unique=True, index=True)
    commission_bps = Column(Integer, nullable=False, default=1000)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class StreamerProductAssignment(Base):
    __tablename__ = "tachiya_streamer_product_assignments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    saleor_product_id = Column(String, nullable=False, unique=True, index=True)
    streamer_profile_id = Column(
        String,
        ForeignKey("tachiya_streamer_profiles.id"),
        nullable=False,
        index=True,
    )
    streamer_slug = Column(String, nullable=False, index=True)
    source = Column(String, nullable=False, default="manual")
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class StreamerRevenueShareRecord(Base):
    __tablename__ = "tachiya_streamer_revenue_share_records"
    __table_args__ = (
        UniqueConstraint(
            "order_id",
            "streamer_slug",
            name="uq_tachiya_streamer_revenue_share_order_streamer",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String, nullable=False, index=True)
    streamer_profile_id = Column(
        String,
        ForeignKey("tachiya_streamer_profiles.id"),
        nullable=False,
        index=True,
    )
    streamer_slug = Column(String, nullable=False, index=True)
    gross_amount = Column(Integer, nullable=False)
    commission_bps = Column(Integer, nullable=False)
    share_amount = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="pending", index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
