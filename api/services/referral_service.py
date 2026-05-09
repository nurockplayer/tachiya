from sqlalchemy.orm import Session

from models.referral import ReferralRelationship, ReferralReward
from services.points_service import PointsService


class ReferralService:
    def __init__(self, db: Session, reward_rate: float = 0.05):
        self.db = db
        self.reward_rate = reward_rate
        self.points_service = PointsService(db)

    async def process_referral_reward(
        self,
        order_id: str,
        referee_id: str,
        order_total_amount: int,
    ) -> ReferralReward | None:
        if order_total_amount <= 0:
            raise ValueError("order_total_amount must be positive")

        existing_order_reward = (
            self.db.query(ReferralReward)
            .filter(ReferralReward.order_id == order_id)
            .first()
        )
        if existing_order_reward:
            return existing_order_reward

        relationship = (
            self.db.query(ReferralRelationship)
            .filter(ReferralRelationship.referee_id == referee_id)
            .first()
        )
        if relationship is None:
            return None

        existing_referee_reward = (
            self.db.query(ReferralReward)
            .filter(ReferralReward.referee_id == referee_id)
            .first()
        )
        if existing_referee_reward:
            return None

        reward_points = int(order_total_amount * self.reward_rate)
        if reward_points <= 0:
            return None

        ledger_entry = await self.points_service.credit(
            user_id=relationship.referrer_id,
            amount=reward_points,
            reference_id=f"referral:{order_id}",
            source_type="referral",
        )

        reward = ReferralReward(
            order_id=order_id,
            referrer_id=relationship.referrer_id,
            referee_id=referee_id,
            order_total_amount=order_total_amount,
            reward_points=reward_points,
            ledger_entry_id=ledger_entry.id,
        )
        self.db.add(reward)
        self.db.commit()
        self.db.refresh(reward)
        return reward
