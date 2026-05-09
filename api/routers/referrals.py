from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models.webhook_event import WebhookEvent
from security import VerifiedWebhookRequest, verify_internal_secret, verify_webhook_signature
from services.referral_service import ReferralService

router = APIRouter(prefix="/referrals", tags=["referrals"])


class OrderCompletedRequest(BaseModel):
    order_id: str
    referee_id: str
    order_total_amount: int


class ReferralRewardResponse(BaseModel):
    rewarded: bool
    reward_points: int | None = None
    ledger_entry_id: str | None = None


@router.post(
    "/webhooks/order-completed",
    response_model=ReferralRewardResponse,
    dependencies=[Depends(verify_internal_secret)],
)
async def order_completed_webhook(
    req: OrderCompletedRequest,
    webhook: VerifiedWebhookRequest | None = Depends(verify_webhook_signature),
    db: Session = Depends(get_db),
):
    _reject_replayed_webhook_event(db, webhook)

    try:
        reward = await ReferralService(db).process_referral_reward(
            order_id=req.order_id,
            referee_id=req.referee_id,
            order_total_amount=req.order_total_amount,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _record_webhook_event(db, webhook, event_type="referral.order_completed")

    if reward is None:
        return ReferralRewardResponse(rewarded=False)

    return ReferralRewardResponse(
        rewarded=True,
        reward_points=reward.reward_points,
        ledger_entry_id=reward.ledger_entry_id,
    )


def _reject_replayed_webhook_event(
    db: Session,
    webhook: VerifiedWebhookRequest | None,
) -> None:
    if webhook is None:
        return

    existing_event = (
        db.query(WebhookEvent)
        .filter(WebhookEvent.event_id == webhook.event_id)
        .first()
    )
    if existing_event is not None:
        raise HTTPException(status_code=409, detail="webhook event already processed")


def _record_webhook_event(
    db: Session,
    webhook: VerifiedWebhookRequest | None,
    *,
    event_type: str,
) -> None:
    if webhook is None:
        return

    event = WebhookEvent(
        event_id=webhook.event_id,
        event_type=event_type,
        occurred_at=webhook.occurred_at,
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="webhook event already processed",
        ) from exc
