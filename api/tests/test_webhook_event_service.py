import sys
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.webhook_event import WebhookEvent
from security import VerifiedWebhookRequest
from services.webhook_event_service import WebhookEventReplayError, WebhookEventService


def build_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_record_event_persists_verified_webhook_event():
    session = build_session()
    webhook = VerifiedWebhookRequest(
        event_id="evt-1",
        occurred_at=datetime(2026, 1, 1, 0, 0, 0),
    )

    WebhookEventService(session).record_event(webhook, event_type="points.order_rewarded")

    event = session.query(WebhookEvent).one()
    assert event.event_id == "evt-1"
    assert event.event_type == "points.order_rewarded"
    assert event.occurred_at == datetime(2026, 1, 1, 0, 0, 0)


def test_record_event_normalizes_identifiers():
    session = build_session()
    webhook = VerifiedWebhookRequest(
        event_id=" evt-1 ",
        occurred_at=datetime(2026, 1, 1, 0, 0, 0),
    )

    WebhookEventService(session).record_event(webhook, event_type=" points.order_rewarded ")

    event = session.query(WebhookEvent).one()
    assert event.event_id == "evt-1"
    assert event.event_type == "points.order_rewarded"


def test_record_event_ignores_unsigned_webhook_when_secret_is_not_configured():
    session = build_session()

    WebhookEventService(session).record_event(None, event_type="points.order_rewarded")

    assert session.query(WebhookEvent).count() == 0


def test_reject_replayed_event_raises_for_existing_event_id():
    session = build_session()
    webhook = VerifiedWebhookRequest(
        event_id="evt-1",
        occurred_at=datetime(2026, 1, 1, 0, 0, 0),
    )
    service = WebhookEventService(session)
    service.record_event(webhook, event_type="points.order_rewarded")

    with pytest.raises(WebhookEventReplayError, match="webhook event already processed"):
        service.reject_replayed_event(webhook)


def test_reject_replayed_event_rejects_blank_event_id():
    session = build_session()
    webhook = VerifiedWebhookRequest(
        event_id=" ",
        occurred_at=datetime(2026, 1, 1, 0, 0, 0),
    )

    with pytest.raises(ValueError, match="webhook event_id is required"):
        WebhookEventService(session).reject_replayed_event(webhook)


def test_record_event_rejects_blank_event_id():
    session = build_session()
    webhook = VerifiedWebhookRequest(
        event_id=" ",
        occurred_at=datetime(2026, 1, 1, 0, 0, 0),
    )

    with pytest.raises(ValueError, match="webhook event_id is required"):
        WebhookEventService(session).record_event(webhook, event_type="points.order_rewarded")

    assert session.query(WebhookEvent).count() == 0


def test_record_event_rejects_blank_event_type():
    session = build_session()
    webhook = VerifiedWebhookRequest(
        event_id="evt-1",
        occurred_at=datetime(2026, 1, 1, 0, 0, 0),
    )

    with pytest.raises(ValueError, match="webhook event_type is required"):
        WebhookEventService(session).record_event(webhook, event_type=" ")

    assert session.query(WebhookEvent).count() == 0


def test_record_event_raises_for_unique_conflict():
    session = build_session()
    webhook = VerifiedWebhookRequest(
        event_id="evt-1",
        occurred_at=datetime(2026, 1, 1, 0, 0, 0),
    )
    service = WebhookEventService(session)
    service.record_event(webhook, event_type="points.order_rewarded")

    with pytest.raises(WebhookEventReplayError, match="webhook event already processed"):
        service.record_event(webhook, event_type="points.order_rewarded")


def test_list_events_filters_by_event_type_and_orders_recent_first():
    session = build_session()
    service = WebhookEventService(session)
    service.record_event(
        VerifiedWebhookRequest(
            event_id="evt-1",
            occurred_at=datetime(2026, 1, 1, 0, 0, 0),
        ),
        event_type="points.order_rewarded",
    )
    service.record_event(
        VerifiedWebhookRequest(
            event_id="evt-2",
            occurred_at=datetime(2026, 1, 2, 0, 0, 0),
        ),
        event_type="revenue_share.order_completed",
    )
    service.record_event(
        VerifiedWebhookRequest(
            event_id="evt-3",
            occurred_at=datetime(2026, 1, 3, 0, 0, 0),
        ),
        event_type=" points.order_rewarded ",
    )

    events = service.list_events(event_type=" points.order_rewarded ", limit=10)

    assert [event.event_id for event in events] == ["evt-3", "evt-1"]


def test_list_events_filters_event_id():
    session = build_session()
    service = WebhookEventService(session)
    session.add_all(
        [
            WebhookEvent(
                event_id="evt-other",
                event_type="points.order_rewarded",
                occurred_at=datetime(2026, 1, 1, 0, 0, 0),
                received_at=datetime(2026, 1, 1, 0, 0, 1),
            ),
            WebhookEvent(
                event_id="evt-target",
                event_type="points.order_rewarded",
                occurred_at=datetime(2026, 1, 2, 0, 0, 0),
                received_at=datetime(2026, 1, 2, 0, 0, 1),
            ),
        ],
    )
    session.commit()

    events = service.list_events(event_id=" evt-target ", limit=10)

    assert [event.event_id for event in events] == ["evt-target"]


def test_list_events_filters_received_range_inclusively():
    session = build_session()
    service = WebhookEventService(session)
    session.add_all(
        [
            WebhookEvent(
                event_id="evt-before",
                event_type="points.order_rewarded",
                occurred_at=datetime(2026, 1, 1, 0, 0, 0),
                received_at=datetime(2026, 1, 1, 23, 59, 59),
            ),
            WebhookEvent(
                event_id="evt-start",
                event_type="points.order_rewarded",
                occurred_at=datetime(2026, 1, 2, 0, 0, 0),
                received_at=datetime(2026, 1, 2, 0, 0, 0),
            ),
            WebhookEvent(
                event_id="evt-end",
                event_type="points.order_rewarded",
                occurred_at=datetime(2026, 1, 3, 0, 0, 0),
                received_at=datetime(2026, 1, 3, 0, 0, 0),
            ),
            WebhookEvent(
                event_id="evt-after",
                event_type="points.order_rewarded",
                occurred_at=datetime(2026, 1, 4, 0, 0, 0),
                received_at=datetime(2026, 1, 3, 0, 0, 1),
            ),
        ],
    )
    session.commit()

    events = service.list_events(
        received_from=datetime(2026, 1, 2, 0, 0, 0),
        received_to=datetime(2026, 1, 3, 0, 0, 0),
        limit=10,
    )

    assert [event.event_id for event in events] == ["evt-end", "evt-start"]


def test_list_events_rejects_invalid_received_range():
    session = build_session()
    service = WebhookEventService(session)

    with pytest.raises(ValueError, match="invalid received_at range"):
        service.list_events(
            received_from=datetime(2026, 1, 3, 0, 0, 0),
            received_to=datetime(2026, 1, 2, 0, 0, 0),
        )


@pytest.mark.parametrize("limit", [0, 101, True])
def test_list_events_rejects_invalid_limit(limit):
    session = build_session()

    with pytest.raises(ValueError, match="limit must be between 1 and 100"):
        WebhookEventService(session).list_events(limit=limit)
