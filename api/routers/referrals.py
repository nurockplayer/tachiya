from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StrictInt, StringConstraints
from sqlalchemy.orm import Session

from database import get_db
from security import VerifiedWebhookRequest, verify_internal_secret, verify_webhook_signature
from services.referral_service import ReferralService
from services.webhook_event_service import WebhookEventReplayError, WebhookEventService

router = APIRouter(prefix="/referrals", tags=["referrals"])

NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class OrderCompletedRequest(BaseModel):
    order_id: NonBlankStr
    referee_id: NonBlankStr
    order_total_amount: StrictInt = Field(gt=0)


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
    try:
        WebhookEventService(db).reject_replayed_event(webhook)
    except WebhookEventReplayError as exc:
        raise HTTPException(status_code=409, detail="webhook event already processed") from exc


def _record_webhook_event(
    db: Session,
    webhook: VerifiedWebhookRequest | None,
    *,
    event_type: str,
) -> None:
    try:
        WebhookEventService(db).record_event(webhook, event_type=event_type)
    except WebhookEventReplayError as exc:
        raise HTTPException(
            status_code=409,
            detail="webhook event already processed",
        ) from exc
