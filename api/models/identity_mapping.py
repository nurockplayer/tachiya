import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, String, UniqueConstraint

from database import Base


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class IdentityMapping(Base):
    __tablename__ = "tachiya_identity_mappings"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "external_subject",
            name="uq_tachiya_identity_provider_subject",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    saleor_customer_id = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False, index=True)
    external_subject = Column(String, nullable=False, index=True)
    verified_at = Column(DateTime, default=utcnow, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    unlinked_at = Column(DateTime, nullable=True)
