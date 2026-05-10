from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.identity_audit_event import IdentityAuditEvent
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
        *,
        actor: str = "system",
        reason: str | None = None,
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
        self._record_audit_event(
            action="identity.linked",
            actor=actor,
            source=self._identity_source(normalized_provider, normalized_external_subject),
            target=self._saleor_target(normalized_saleor_customer_id),
            reason=reason,
        )
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

    def unlink_identity(
        self,
        mapping_id: str,
        *,
        actor: str = "system",
        reason: str | None = None,
    ) -> IdentityMapping:
        mapping = self.db.get(IdentityMapping, mapping_id)
        if mapping is None:
            raise ValueError("identity mapping not found")

        if mapping.unlinked_at is None:
            mapping.unlinked_at = utcnow()
            self._record_audit_event(
                action="identity.unlinked",
                actor=actor,
                source=self._identity_source(mapping.provider, mapping.external_subject),
                target=self._saleor_target(mapping.saleor_customer_id),
                reason=reason,
                commit=False,
            )
            self.db.commit()
            self.db.refresh(mapping)
        return mapping

    def list_mappings(
        self,
        *,
        provider: str | None = None,
        saleor_customer_id: str | None = None,
        include_unlinked: bool = False,
        limit: int = 20,
    ) -> list[IdentityMapping]:
        normalized_provider = (
            self._normalize_provider(provider)
            if provider is not None
            else None
        )
        normalized_saleor_customer_id = self._normalize_optional_filter(
            saleor_customer_id,
            "saleor_customer_id is required",
        )

        query = self.db.query(IdentityMapping)
        if normalized_provider is not None:
            query = query.filter(IdentityMapping.provider == normalized_provider)
        if normalized_saleor_customer_id is not None:
            query = query.filter(
                IdentityMapping.saleor_customer_id == normalized_saleor_customer_id,
            )
        if not include_unlinked:
            query = query.filter(IdentityMapping.unlinked_at.is_(None))

        return (
            query.order_by(IdentityMapping.created_at.desc(), IdentityMapping.id.asc())
            .limit(limit)
            .all()
        )

    def list_audit_events(self, limit: int = 20) -> list[IdentityAuditEvent]:
        return (
            self.db.query(IdentityAuditEvent)
            .order_by(IdentityAuditEvent.created_at.desc(), IdentityAuditEvent.id.desc())
            .limit(limit)
            .all()
        )

    def _record_audit_event(
        self,
        *,
        action: str,
        actor: str,
        source: str,
        target: str,
        reason: str | None,
        commit: bool = True,
    ) -> IdentityAuditEvent:
        event = IdentityAuditEvent(
            action=action,
            actor=self._normalize_required(actor, "actor is required"),
            source=source,
            target=target,
            reason=reason.strip() if reason else None,
        )
        self.db.add(event)
        if commit:
            self.db.commit()
            self.db.refresh(event)
        return event

    @staticmethod
    def _identity_source(provider: str, external_subject: str) -> str:
        return f"{provider}:{external_subject}"

    @staticmethod
    def _saleor_target(saleor_customer_id: str) -> str:
        return f"saleor:{saleor_customer_id}"

    @staticmethod
    def _normalize_provider(provider: str) -> str:
        return IdentityMappingService._normalize_required(provider, "provider is required").lower()

    @staticmethod
    def _normalize_required(value: str, message: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(message)
        return normalized

    @staticmethod
    def _normalize_optional_filter(value: str | None, message: str) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError(message)
        return normalized
