import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, String

from database import Base


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class IdentityAuditEvent(Base):
    __tablename__ = "tachiya_identity_audit_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    action = Column(String, nullable=False, index=True)
    actor = Column(String, nullable=False, index=True)
    source = Column(String, nullable=False, index=True)
    target = Column(String, nullable=False, index=True)
    reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
