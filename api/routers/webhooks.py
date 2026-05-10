from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from security import verify_internal_secret
from services.webhook_event_service import WebhookEventService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookEventResponse(BaseModel):
    id: str
    event_id: str
    event_type: str
    occurred_at: datetime
    received_at: datetime


class WebhookEventsResponse(BaseModel):
    events: list[WebhookEventResponse]


@router.get(
    "/events",
    response_model=WebhookEventsResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def list_webhook_events(
    event_type: str | None = Query(default=None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    try:
        events = WebhookEventService(db).list_events(
            event_type=event_type,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return WebhookEventsResponse(
        events=[
            WebhookEventResponse(
                id=event.id,
                event_id=event.event_id,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
                received_at=event.received_at,
            )
            for event in events
        ],
    )
