from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.identity_mapping import IdentityMapping


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class IdentityMappingService:
    def __init__(self, db: Session):
        self.db = db

    def link_identity(
        self,
        saleor_customer_id: str,
        provider: str,
        external_subject: str,
    ) -> IdentityMapping:
        normalized_saleor_customer_id = self._normalize_required(
            saleor_customer_id,
            "saleor_customer_id is required",
        )
        normalized_provider = self._normalize_provider(provider)
        normalized_external_subject = self._normalize_required(
            external_subject,
            "external_subject is required",
        )

        existing_provider_mapping = (
            self.db.query(IdentityMapping)
            .filter(
                IdentityMapping.saleor_customer_id == normalized_saleor_customer_id,
                IdentityMapping.provider == normalized_provider,
                IdentityMapping.unlinked_at.is_(None),
            )
            .first()
        )
        if existing_provider_mapping is not None:
            raise ValueError("saleor customer already has active provider mapping")

        mapping = IdentityMapping(
            saleor_customer_id=normalized_saleor_customer_id,
            provider=normalized_provider,
            external_subject=normalized_external_subject,
        )
        self.db.add(mapping)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("identity mapping already exists") from exc
        self.db.refresh(mapping)
        return mapping

    def resolve_customer_id(self, provider: str, external_subject: str) -> str | None:
        mapping = (
            self.db.query(IdentityMapping)
            .filter(
                IdentityMapping.provider == self._normalize_provider(provider),
                IdentityMapping.external_subject
                == self._normalize_required(external_subject, "external_subject is required"),
                IdentityMapping.unlinked_at.is_(None),
            )
            .first()
        )
        return mapping.saleor_customer_id if mapping is not None else None

    def unlink_identity(self, mapping_id: str) -> IdentityMapping:
        mapping = self.db.get(IdentityMapping, mapping_id)
        if mapping is None:
            raise ValueError("identity mapping not found")

        if mapping.unlinked_at is None:
            mapping.unlinked_at = utcnow()
            self.db.commit()
            self.db.refresh(mapping)
        return mapping

    @staticmethod
    def _normalize_provider(provider: str) -> str:
        return IdentityMappingService._normalize_required(provider, "provider is required").lower()

    @staticmethod
    def _normalize_required(value: str, message: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(message)
        return normalized
