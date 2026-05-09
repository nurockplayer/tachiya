from datetime import datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.points_ledger import PointsLedger


class PointsService:
    def __init__(self, db: Session):
        self.db = db

    async def credit(
        self,
        user_id: str,
        amount: int,
        reference_id: str,
        *,
        source_type: str = "manual",
        expires_at: datetime | None = None,
    ) -> PointsLedger:
        self._validate_positive_amount(amount)
        normalized_source_type = self._validate_source_type(source_type)
        existing_entry = self._find_idempotent_entry(
            user_id=user_id,
            entry_type="credit",
            reference_id=reference_id,
        )
        if existing_entry is not None:
            return self._ensure_idempotent_entry_matches(
                existing_entry,
                amount=amount,
                source_type=normalized_source_type,
                expires_at=expires_at,
            )

        return self._create_entry(
            user_id=user_id,
            amount=amount,
            entry_type="credit",
            reference_id=reference_id,
            source_type=normalized_source_type,
            expires_at=expires_at,
        )

    async def debit(
        self,
        user_id: str,
        amount: int,
        reference_id: str,
        *,
        source_type: str = "manual",
        expires_at: datetime | None = None,
    ) -> PointsLedger:
        self._validate_positive_amount(amount)
        normalized_source_type = self._validate_source_type(source_type)
        existing_entry = self._find_idempotent_entry(
            user_id=user_id,
            entry_type="debit",
            reference_id=reference_id,
        )
        if existing_entry is not None:
            return self._ensure_idempotent_entry_matches(
                existing_entry,
                amount=-amount,
                source_type=normalized_source_type,
                expires_at=expires_at,
            )

        balance = await self.get_balance(user_id)
        if balance < amount:
            raise ValueError("insufficient balance")

        return self._create_entry(
            user_id=user_id,
            amount=-amount,
            entry_type="debit",
            reference_id=reference_id,
            source_type=normalized_source_type,
            expires_at=expires_at,
        )

    async def get_balance(self, user_id: str) -> int:
        balance = (
            self.db.query(func.coalesce(func.sum(PointsLedger.amount), 0))
            .filter(PointsLedger.user_id == user_id)
            .scalar()
        )
        return int(balance or 0)

    async def list_entries(self, user_id: str, limit: int = 20) -> list[PointsLedger]:
        return (
            self.db.query(PointsLedger)
            .filter(PointsLedger.user_id == user_id)
            .order_by(PointsLedger.created_at.desc(), PointsLedger.id.desc())
            .limit(limit)
            .all()
        )

    def _create_entry(
        self,
        *,
        user_id: str,
        amount: int,
        entry_type: str,
        reference_id: str,
        source_type: str,
        expires_at: datetime | None,
    ) -> PointsLedger:
        entry = PointsLedger(
            user_id=user_id,
            amount=amount,
            entry_type=entry_type,
            reference_id=reference_id,
            source_type=source_type,
            expires_at=expires_at,
        )
        self.db.add(entry)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing_entry = self._find_idempotent_entry(
                user_id=user_id,
                entry_type=entry_type,
                reference_id=reference_id,
            )
            if existing_entry is None:
                raise
            return self._ensure_idempotent_entry_matches(
                existing_entry,
                amount=amount,
                source_type=source_type,
                expires_at=expires_at,
            )
        self.db.refresh(entry)
        return entry

    def _find_idempotent_entry(
        self,
        *,
        user_id: str,
        entry_type: str,
        reference_id: str,
    ) -> PointsLedger | None:
        return (
            self.db.query(PointsLedger)
            .filter(
                PointsLedger.user_id == user_id,
                PointsLedger.entry_type == entry_type,
                PointsLedger.reference_id == reference_id,
            )
            .one_or_none()
        )

    @staticmethod
    def _ensure_idempotent_entry_matches(
        entry: PointsLedger,
        *,
        amount: int,
        source_type: str,
        expires_at: datetime | None,
    ) -> PointsLedger:
        if (
            entry.amount != amount
            or entry.source_type != source_type
            or entry.expires_at != expires_at
        ):
            raise ValueError("idempotency key conflict")
        return entry

    @staticmethod
    def _validate_positive_amount(amount: int) -> None:
        if amount <= 0:
            raise ValueError("amount must be positive")

    @staticmethod
    def _validate_source_type(source_type: str) -> str:
        normalized = source_type.strip()
        if not normalized:
            raise ValueError("source_type is required")
        return normalized
