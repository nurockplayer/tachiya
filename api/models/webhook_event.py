import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, String

from database import Base


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class WebhookEvent(Base):
    __tablename__ = "tachiya_webhook_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String, nullable=False, unique=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    occurred_at = Column(DateTime, nullable=False)
    received_at = Column(DateTime, default=utcnow, nullable=False)
