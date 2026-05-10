import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.points_ledger import PointsLedger
from models.referral import ReferralRelationship, ReferralReward


class ReferralService:
    def __init__(self, db: Session, reward_rate: float = 0.05):
        self.db = db
        self.reward_rate = reward_rate

    async def process_referral_reward(
        self,
        order_id: str,
        referee_id: str,
        order_total_amount: int,
    ) -> ReferralReward | None:
        normalized_order_id = self._validate_required(order_id, "order_id is required")
        normalized_referee_id = self._validate_required(referee_id, "referee_id is required")
        normalized_order_total_amount = self._validate_positive_integer(
            order_total_amount,
            "order_total_amount must be a positive integer",
        )

        existing_order_reward = (
            self.db.query(ReferralReward)
            .filter(ReferralReward.order_id == normalized_order_id)
            .first()
        )
        if existing_order_reward:
            return existing_order_reward

        relationship = (
            self.db.query(ReferralRelationship)
            .filter(ReferralRelationship.referee_id == normalized_referee_id)
            .first()
        )
        if relationship is None:
            return None

        existing_referee_reward = (
            self.db.query(ReferralReward)
            .filter(ReferralReward.referee_id == normalized_referee_id)
            .first()
        )
        if existing_referee_reward:
            return None

        reward_points = int(normalized_order_total_amount * self.reward_rate)
        if reward_points <= 0:
            return None

        ledger_entry = PointsLedger(
            id=str(uuid.uuid4()),
            user_id=relationship.referrer_id,
            amount=reward_points,
            entry_type="credit",
            reference_id=f"referral:{normalized_order_id}",
            source_type="referral",
        )

        reward = ReferralReward(
            order_id=normalized_order_id,
            referrer_id=relationship.referrer_id,
            referee_id=normalized_referee_id,
            order_total_amount=normalized_order_total_amount,
            reward_points=reward_points,
            ledger_entry_id=ledger_entry.id,
        )
        self.db.add(ledger_entry)
        self.db.add(reward)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing_order_reward = (
                self.db.query(ReferralReward)
                .filter(ReferralReward.order_id == normalized_order_id)
                .first()
            )
            if existing_order_reward:
                return existing_order_reward
            existing_referee_reward = (
                self.db.query(ReferralReward)
                .filter(ReferralReward.referee_id == normalized_referee_id)
                .first()
            )
            if existing_referee_reward:
                return None
            raise
        self.db.refresh(reward)
        return reward

    @staticmethod
    def _validate_required(value: str, message: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(message)
        return normalized

    @staticmethod
    def _validate_positive_integer(value: int, message: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(message)
        return value
