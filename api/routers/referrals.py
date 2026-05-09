from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from security import verify_internal_secret
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
    db: Session = Depends(get_db),
):
    try:
        reward = await ReferralService(db).process_referral_reward(
            order_id=req.order_id,
            referee_id=req.referee_id,
            order_total_amount=req.order_total_amount,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if reward is None:
        return ReferralRewardResponse(rewarded=False)

    return ReferralRewardResponse(
        rewarded=True,
        reward_points=reward.reward_points,
        ledger_entry_id=reward.ledger_entry_id,
    )
