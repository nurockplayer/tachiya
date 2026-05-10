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

        existing_external_mapping = (
            self.db.query(IdentityMapping)
            .filter(
                IdentityMapping.provider == normalized_provider,
                IdentityMapping.external_subject == normalized_external_subject,
            )
            .first()
        )
        if existing_external_mapping is not None:
            if existing_external_mapping.unlinked_at is None:
                raise ValueError("identity mapping already exists")

            existing_external_mapping.saleor_customer_id = normalized_saleor_customer_id
            existing_external_mapping.verified_at = utcnow()
            existing_external_mapping.unlinked_at = None
            self._record_audit_event(
                action="identity.relinked",
                actor=actor,
                source=self._identity_source(
                    normalized_provider,
                    normalized_external_subject,
                ),
                target=self._saleor_target(normalized_saleor_customer_id),
                reason=reason,
                commit=False,
            )
            self.db.commit()
            self.db.refresh(existing_external_mapping)
            return existing_external_mapping

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
        external_subject: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
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
        normalized_external_subject = self._normalize_optional_filter(
            external_subject,
            "external_subject is required",
        )
        normalized_created_from = self._normalize_optional_datetime(created_from)
        normalized_created_to = self._normalize_optional_datetime(created_to)
        if (
            normalized_created_from is not None
            and normalized_created_to is not None
            and normalized_created_from > normalized_created_to
        ):
            raise ValueError("invalid created_at range")

        query = self.db.query(IdentityMapping)
        if normalized_provider is not None:
            query = query.filter(IdentityMapping.provider == normalized_provider)
        if normalized_saleor_customer_id is not None:
            query = query.filter(
                IdentityMapping.saleor_customer_id == normalized_saleor_customer_id,
            )
        if normalized_external_subject is not None:
            query = query.filter(IdentityMapping.external_subject == normalized_external_subject)
        if normalized_created_from is not None:
            query = query.filter(IdentityMapping.created_at >= normalized_created_from)
        if normalized_created_to is not None:
            query = query.filter(IdentityMapping.created_at <= normalized_created_to)
        if not include_unlinked:
            query = query.filter(IdentityMapping.unlinked_at.is_(None))

        return (
            query.order_by(IdentityMapping.created_at.desc(), IdentityMapping.id.asc())
            .limit(limit)
            .all()
        )

    def list_audit_events(
        self,
        *,
        action: str | None = None,
        actor: str | None = None,
        source: str | None = None,
        target: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int = 20,
    ) -> list[IdentityAuditEvent]:
        normalized_action = self._normalize_optional_filter(action, "action is required")
        normalized_actor = self._normalize_optional_filter(actor, "actor is required")
        normalized_source = self._normalize_optional_filter(source, "source is required")
        normalized_target = self._normalize_optional_filter(target, "target is required")
        normalized_created_from = self._normalize_optional_datetime(created_from)
        normalized_created_to = self._normalize_optional_datetime(created_to)
        if (
            normalized_created_from is not None
            and normalized_created_to is not None
            and normalized_created_from > normalized_created_to
        ):
            raise ValueError("invalid created_at range")

        query = self.db.query(IdentityAuditEvent)
        if normalized_action is not None:
            query = query.filter(IdentityAuditEvent.action == normalized_action)
        if normalized_actor is not None:
            query = query.filter(IdentityAuditEvent.actor == normalized_actor)
        if normalized_source is not None:
            query = query.filter(IdentityAuditEvent.source == normalized_source)
        if normalized_target is not None:
            query = query.filter(IdentityAuditEvent.target == normalized_target)
        if normalized_created_from is not None:
            query = query.filter(IdentityAuditEvent.created_at >= normalized_created_from)
        if normalized_created_to is not None:
            query = query.filter(IdentityAuditEvent.created_at <= normalized_created_to)

        return (
            query.order_by(IdentityAuditEvent.created_at.desc(), IdentityAuditEvent.id.desc())
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
            reason=self._normalize_optional_text(reason),
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

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _normalize_optional_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)
