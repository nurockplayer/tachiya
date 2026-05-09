import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

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
