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

        event_id = self._validate_required(webhook.event_id, "webhook event_id is required")
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

        event_id = self._validate_required(webhook.event_id, "webhook event_id is required")
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

    @staticmethod
    def _validate_required(value: str, message: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(message)
        return normalized
