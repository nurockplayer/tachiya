from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.points_ledger import PointsLedger


@dataclass
class PointsBucket:
    entry: PointsLedger
    amount: int
    expires_at: datetime | None


@dataclass(frozen=True)
class ExpiredCreditExposure:
    entry: PointsLedger
    remaining_amount: int


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
        normalized_user_id = self._validate_required(user_id, "user_id is required")
        normalized_reference_id = self._validate_required(reference_id, "reference_id is required")
        self._validate_positive_amount(amount)
        normalized_source_type = self._validate_source_type(source_type)
        existing_entry = self._find_idempotent_entry(
            user_id=normalized_user_id,
            entry_type="credit",
            reference_id=normalized_reference_id,
        )
        if existing_entry is not None:
            return self._ensure_idempotent_entry_matches(
                existing_entry,
                amount=amount,
                source_type=normalized_source_type,
                expires_at=expires_at,
            )

        return self._create_entry(
            user_id=normalized_user_id,
            amount=amount,
            entry_type="credit",
            reference_id=normalized_reference_id,
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
        normalized_user_id = self._validate_required(user_id, "user_id is required")
        normalized_reference_id = self._validate_required(reference_id, "reference_id is required")
        self._validate_positive_amount(amount)
        normalized_source_type = self._validate_source_type(source_type)
        existing_entry = self._find_idempotent_entry(
            user_id=normalized_user_id,
            entry_type="debit",
            reference_id=normalized_reference_id,
        )
        if existing_entry is not None:
            return self._ensure_idempotent_entry_matches(
                existing_entry,
                amount=-amount,
                source_type=normalized_source_type,
                expires_at=expires_at,
            )

        balance = await self.get_balance(normalized_user_id)
        if balance < amount:
            raise ValueError("insufficient balance")

        return self._create_entry(
            user_id=normalized_user_id,
            amount=-amount,
            entry_type="debit",
            reference_id=normalized_reference_id,
            source_type=normalized_source_type,
            expires_at=expires_at,
        )

    async def get_balance(self, user_id: str, *, at: datetime | None = None) -> int:
        effective_at = self._normalize_datetime(at or datetime.now(UTC))
        buckets, debit_deficit = self._build_credit_buckets(user_id, at=effective_at)

        active_balance = sum(
            bucket.amount
            for bucket in buckets
            if not self._is_expired(
                bucket.expires_at,
                effective_at,
            )
        )
        return int(active_balance - debit_deficit)

    def list_expired_credit_exposures(
        self,
        user_id: str,
        *,
        at: datetime | None = None,
        limit: int = 20,
    ) -> list[ExpiredCreditExposure]:
        normalized_user_id = self._validate_required(user_id, "user_id is required")
        effective_at = self._normalize_datetime(at or datetime.now(UTC))
        buckets, _debit_deficit = self._build_credit_buckets(
            normalized_user_id,
            at=effective_at,
        )
        exposures = [
            ExpiredCreditExposure(entry=bucket.entry, remaining_amount=bucket.amount)
            for bucket in buckets
            if bucket.amount > 0 and self._is_expired(bucket.expires_at, effective_at)
        ]
        exposures.sort(
            key=lambda exposure: (
                exposure.entry.expires_at or datetime.max,
                exposure.entry.created_at,
                exposure.entry.id,
            ),
        )
        return exposures[:limit]

    async def list_entries(self, user_id: str, limit: int = 20) -> list[PointsLedger]:
        return (
            self.db.query(PointsLedger)
            .filter(PointsLedger.user_id == user_id)
            .order_by(PointsLedger.created_at.desc(), PointsLedger.id.desc())
            .limit(limit)
            .all()
        )

    def list_admin_entries(
        self,
        *,
        user_id: str | None = None,
        entry_type: str | None = None,
        source_type: str | None = None,
        reference_id: str | None = None,
        limit: int = 20,
    ) -> list[PointsLedger]:
        normalized_user_id = self._normalize_optional_filter(user_id, "user_id is required")
        normalized_entry_type = (
            self._validate_entry_type(entry_type)
            if entry_type is not None
            else None
        )
        normalized_source_type = (
            self._validate_source_type(source_type)
            if source_type is not None
            else None
        )
        normalized_reference_id = self._normalize_optional_filter(
            reference_id,
            "reference_id is required",
        )

        query = self.db.query(PointsLedger)
        if normalized_user_id is not None:
            query = query.filter(PointsLedger.user_id == normalized_user_id)
        if normalized_entry_type is not None:
            query = query.filter(PointsLedger.entry_type == normalized_entry_type)
        if normalized_source_type is not None:
            query = query.filter(PointsLedger.source_type == normalized_source_type)
        if normalized_reference_id is not None:
            query = query.filter(PointsLedger.reference_id == normalized_reference_id)

        return (
            query.order_by(PointsLedger.created_at.desc(), PointsLedger.id.desc())
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
        return normalized.lower()

    @staticmethod
    def _validate_entry_type(entry_type: str) -> str:
        normalized = entry_type.strip().lower()
        if normalized not in {"credit", "debit"}:
            raise ValueError("entry_type must be credit or debit")
        return normalized

    @staticmethod
    def _validate_required(value: str, message: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(message)
        return normalized

    @staticmethod
    def _normalize_optional_filter(value: str | None, message: str) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError(message)
        return normalized

    def _build_credit_buckets(
        self,
        user_id: str,
        *,
        at: datetime,
    ) -> tuple[list[PointsBucket], int]:
        entries = (
            self.db.query(PointsLedger)
            .filter(
                PointsLedger.user_id == user_id,
                PointsLedger.created_at <= at,
            )
            .order_by(PointsLedger.created_at.asc(), PointsLedger.id.asc())
            .all()
        )
        buckets: list[PointsBucket] = []
        debit_deficit = 0

        for entry in entries:
            if entry.amount > 0:
                buckets.append(
                    PointsBucket(
                        entry=entry,
                        amount=entry.amount,
                        expires_at=self._normalize_optional_datetime(entry.expires_at),
                    ),
                )
                continue

            if entry.amount >= 0:
                continue

            debit_remaining = abs(entry.amount)
            entry_created_at = self._normalize_datetime(entry.created_at)
            for bucket in self._spendable_buckets(buckets, at=entry_created_at):
                spent = min(bucket.amount, debit_remaining)
                bucket.amount -= spent
                debit_remaining -= spent
                if debit_remaining == 0:
                    break

            debit_deficit += debit_remaining

        return buckets, debit_deficit

    @classmethod
    def _spendable_buckets(
        cls,
        buckets: list[PointsBucket],
        *,
        at: datetime,
    ) -> list[PointsBucket]:
        active_buckets = [
            (index, bucket)
            for index, bucket in enumerate(buckets)
            if bucket.amount > 0
            and not cls._is_expired(
                bucket.expires_at,
                at,
            )
        ]
        active_buckets.sort(
            key=lambda indexed_bucket: cls._expiration_sort_key(
                indexed_bucket[1].expires_at,
                indexed_bucket[0],
            ),
        )
        return [bucket for _, bucket in active_buckets]

    @staticmethod
    def _expiration_sort_key(expires_at: datetime | None, index: int):
        return (expires_at is None, expires_at or datetime.max, index)

    @staticmethod
    def _is_expired(expires_at: datetime | None, at: datetime) -> bool:
        return expires_at is not None and expires_at <= at

    @classmethod
    def _normalize_optional_datetime(cls, value) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return cls._normalize_datetime(value)
        return value

    @staticmethod
    def _normalize_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)
