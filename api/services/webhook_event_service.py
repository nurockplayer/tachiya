from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.webhook_event import WebhookEvent
from security import VerifiedWebhookRequest


class WebhookEventReplayError(ValueError):
    pass


class WebhookEventService:
    def __init__(self, db: Session):
        self.db = db

    def reject_replayed_event(self, webhook: VerifiedWebhookRequest | None) -> None:
        if webhook is None:
            return

        event_id = self._validate_required(
            webhook.event_id, "webhook event_id is required"
        )
        existing_event = (
            self.db.query(WebhookEvent)
            .filter(WebhookEvent.event_id == event_id)
            .first()
        )
        if existing_event is not None:
            raise WebhookEventReplayError("webhook event already processed")

    def record_event(
        self,
        webhook: VerifiedWebhookRequest | None,
        *,
        event_type: str,
    ) -> None:
        if webhook is None:
            return

        event_id = self._validate_required(
            webhook.event_id, "webhook event_id is required"
        )
        normalized_event_type = self._validate_required(
            event_type,
            "webhook event_type is required",
        )
        event = WebhookEvent(
            event_id=event_id,
            event_type=normalized_event_type,
            occurred_at=webhook.occurred_at,
        )
        self.db.add(event)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise WebhookEventReplayError("webhook event already processed") from exc

    def list_events(
        self,
        *,
        event_id: str | None = None,
        event_type: str | None = None,
        received_from: datetime | None = None,
        received_to: datetime | None = None,
        limit: int = 20,
    ) -> list[WebhookEvent]:
        normalized_limit = self._validate_read_limit(limit)
        normalized_event_id = (
            self._validate_required(event_id, "event_id is required")
            if event_id is not None
            else None
        )
        normalized_event_type = (
            self._validate_required(event_type, "event_type is required")
            if event_type is not None
            else None
        )
        normalized_received_from = self._normalize_optional_datetime(received_from)
        normalized_received_to = self._normalize_optional_datetime(received_to)
        if (
            normalized_received_from is not None
            and normalized_received_to is not None
            and normalized_received_from > normalized_received_to
        ):
            raise ValueError("invalid received_at range")

        query = self.db.query(WebhookEvent)
        if normalized_event_id is not None:
            query = query.filter(WebhookEvent.event_id == normalized_event_id)
        if normalized_event_type is not None:
            query = query.filter(WebhookEvent.event_type == normalized_event_type)
        if normalized_received_from is not None:
            query = query.filter(WebhookEvent.received_at >= normalized_received_from)
        if normalized_received_to is not None:
            query = query.filter(WebhookEvent.received_at <= normalized_received_to)

        return (
            query.order_by(WebhookEvent.received_at.desc(), WebhookEvent.id.desc())
            .limit(normalized_limit)
            .all()
        )

    @staticmethod
    def _validate_required(value: str, message: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(message)
        return normalized

    @staticmethod
    def _normalize_optional_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    @staticmethod
    def _validate_read_limit(limit: int) -> int:
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 100
        ):
            raise ValueError("limit must be between 1 and 100")
        return limit
