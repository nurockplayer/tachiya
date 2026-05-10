from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.streamer import (
    StreamerProductAssignment,
    StreamerProfile,
    StreamerRevenueShareRecord,
)

REVENUE_SHARE_RECORD_STATUSES = {"pending", "paid", "void"}
REVENUE_SHARE_TERMINAL_STATUSES = {"paid", "void"}


@dataclass(frozen=True)
class RevenueShareLine:
    saleor_product_id: str
    gross_amount: int


@dataclass(frozen=True)
class StreamerRevenueShare:
    streamer_slug: str
    gross_amount: int
    commission_bps: int
    share_amount: int


@dataclass(frozen=True)
class RevenueSharePreview:
    order_id: str
    shares: list[StreamerRevenueShare]
    unassigned_product_ids: list[str]


@dataclass(frozen=True)
class RevenueShareRecordResult:
    order_id: str
    records: list[StreamerRevenueShareRecord]
    unassigned_product_ids: list[str]


@dataclass(frozen=True)
class RevenueShareRecordSummary:
    status: str
    record_count: int
    gross_amount: int
    share_amount: int


class RevenueShareService:
    def __init__(self, db: Session):
        self.db = db

    def preview_order_share(
        self,
        *,
        order_id: str,
        lines: list[RevenueShareLine],
    ) -> RevenueSharePreview:
        normalized_order_id = self._validate_required(order_id, "order_id is required")
        shares_by_streamer: dict[str, StreamerRevenueShare] = {}
        unassigned_product_ids: list[str] = []
        unassigned_product_id_set: set[str] = set()

        for line in lines:
            product_id = self._validate_required(
                line.saleor_product_id,
                "saleor_product_id is required",
            )
            if line.gross_amount <= 0:
                raise ValueError("gross_amount must be positive")

            assignment = self._get_assignment(product_id)
            if assignment is None:
                self._append_unique_product_id(
                    unassigned_product_ids,
                    unassigned_product_id_set,
                    product_id,
                )
                continue

            streamer = self.db.get(StreamerProfile, assignment.streamer_profile_id)
            if streamer is None or not streamer.active:
                self._append_unique_product_id(
                    unassigned_product_ids,
                    unassigned_product_id_set,
                    product_id,
                )
                continue

            share_amount = line.gross_amount * streamer.commission_bps // 10000
            existing_share = shares_by_streamer.get(streamer.slug)
            if existing_share is None:
                shares_by_streamer[streamer.slug] = StreamerRevenueShare(
                    streamer_slug=streamer.slug,
                    gross_amount=line.gross_amount,
                    commission_bps=streamer.commission_bps,
                    share_amount=share_amount,
                )
                continue

            shares_by_streamer[streamer.slug] = StreamerRevenueShare(
                streamer_slug=streamer.slug,
                gross_amount=existing_share.gross_amount + line.gross_amount,
                commission_bps=streamer.commission_bps,
                share_amount=existing_share.share_amount + share_amount,
            )

        return RevenueSharePreview(
            order_id=normalized_order_id,
            shares=list(shares_by_streamer.values()),
            unassigned_product_ids=unassigned_product_ids,
        )

    def record_order_share(
        self,
        *,
        order_id: str,
        lines: list[RevenueShareLine],
    ) -> RevenueShareRecordResult:
        preview = self.preview_order_share(order_id=order_id, lines=lines)
        records: list[StreamerRevenueShareRecord] = []
        records_to_create: list[StreamerRevenueShareRecord] = []
        for share in preview.shares:
            streamer = self._get_streamer_by_slug(share.streamer_slug)
            if streamer is None:
                raise ValueError("streamer profile not found")

            existing_record = self._get_record(
                order_id=preview.order_id,
                streamer_slug=share.streamer_slug,
            )
            if existing_record is not None:
                records.append(self._ensure_record_matches(existing_record, streamer, share))
                continue

            record = StreamerRevenueShareRecord(
                order_id=preview.order_id,
                streamer_profile_id=streamer.id,
                streamer_slug=share.streamer_slug,
                gross_amount=share.gross_amount,
                commission_bps=share.commission_bps,
                share_amount=share.share_amount,
                status="pending",
            )
            records_to_create.append(record)
            records.append(record)

        if records_to_create:
            self.db.add_all(records_to_create)
            self.db.commit()
            for record in records_to_create:
                self.db.refresh(record)

        return RevenueShareRecordResult(
            order_id=preview.order_id,
            records=records,
            unassigned_product_ids=preview.unassigned_product_ids,
        )

    def list_records(
        self,
        *,
        status: str | None = None,
        streamer_slug: str | None = None,
        order_id: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int = 20,
    ) -> list[StreamerRevenueShareRecord]:
        normalized_limit = self._validate_read_limit(limit)
        normalized_status = (
            self._validate_record_status_filter(status)
            if status is not None
            else None
        )
        normalized_streamer_slug = self._normalize_optional_filter(
            streamer_slug,
            "streamer_slug is required",
        )
        normalized_order_id = self._normalize_optional_filter(order_id, "order_id is required")
        normalized_created_from, normalized_created_to = self._normalize_created_range(
            created_from,
            created_to,
        )

        query = self.db.query(StreamerRevenueShareRecord)
        if normalized_status is not None:
            query = query.filter(StreamerRevenueShareRecord.status == normalized_status)
        if normalized_streamer_slug is not None:
            query = query.filter(StreamerRevenueShareRecord.streamer_slug == normalized_streamer_slug.lower())
        if normalized_order_id is not None:
            query = query.filter(StreamerRevenueShareRecord.order_id == normalized_order_id)
        if normalized_created_from is not None:
            query = query.filter(StreamerRevenueShareRecord.created_at >= normalized_created_from)
        if normalized_created_to is not None:
            query = query.filter(StreamerRevenueShareRecord.created_at <= normalized_created_to)

        return (
            query.order_by(
                StreamerRevenueShareRecord.created_at.desc(),
                StreamerRevenueShareRecord.id.asc(),
            )
            .limit(normalized_limit)
            .all()
        )

    def summarize_records(
        self,
        *,
        status: str | None = None,
        streamer_slug: str | None = None,
        order_id: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> list[RevenueShareRecordSummary]:
        normalized_status = (
            self._validate_record_status_filter(status)
            if status is not None
            else None
        )
        normalized_streamer_slug = self._normalize_optional_filter(
            streamer_slug,
            "streamer_slug is required",
        )
        normalized_order_id = self._normalize_optional_filter(order_id, "order_id is required")
        normalized_created_from, normalized_created_to = self._normalize_created_range(
            created_from,
            created_to,
        )

        query = self.db.query(
            StreamerRevenueShareRecord.status,
            func.count(StreamerRevenueShareRecord.id),
            func.coalesce(func.sum(StreamerRevenueShareRecord.gross_amount), 0),
            func.coalesce(func.sum(StreamerRevenueShareRecord.share_amount), 0),
        )
        if normalized_status is not None:
            query = query.filter(StreamerRevenueShareRecord.status == normalized_status)
        if normalized_streamer_slug is not None:
            query = query.filter(
                StreamerRevenueShareRecord.streamer_slug == normalized_streamer_slug.lower(),
            )
        if normalized_order_id is not None:
            query = query.filter(StreamerRevenueShareRecord.order_id == normalized_order_id)
        if normalized_created_from is not None:
            query = query.filter(StreamerRevenueShareRecord.created_at >= normalized_created_from)
        if normalized_created_to is not None:
            query = query.filter(StreamerRevenueShareRecord.created_at <= normalized_created_to)

        rows = (
            query.group_by(StreamerRevenueShareRecord.status)
            .order_by(StreamerRevenueShareRecord.status.asc())
            .all()
        )
        return [
            RevenueShareRecordSummary(
                status=row[0],
                record_count=int(row[1]),
                gross_amount=int(row[2]),
                share_amount=int(row[3]),
            )
            for row in rows
        ]

    def update_record_status(
        self,
        *,
        record_id: str,
        status: str,
    ) -> StreamerRevenueShareRecord:
        normalized_record_id = self._validate_required(record_id, "record_id is required")
        normalized_status = self._validate_record_status(status)
        record = self.db.get(StreamerRevenueShareRecord, normalized_record_id)
        if record is None:
            raise ValueError("revenue share record not found")
        if record.status == normalized_status:
            return record
        if record.status != "pending":
            raise ValueError("revenue share status conflict")

        record.status = normalized_status
        self.db.commit()
        self.db.refresh(record)
        return record

    def _get_assignment(self, saleor_product_id: str) -> StreamerProductAssignment | None:
        return (
            self.db.query(StreamerProductAssignment)
            .filter(StreamerProductAssignment.saleor_product_id == saleor_product_id)
            .one_or_none()
        )

    def _get_streamer_by_slug(self, slug: str) -> StreamerProfile | None:
        return (
            self.db.query(StreamerProfile)
            .filter(StreamerProfile.slug == slug)
            .one_or_none()
        )

    def _get_record(
        self,
        *,
        order_id: str,
        streamer_slug: str,
    ) -> StreamerRevenueShareRecord | None:
        return (
            self.db.query(StreamerRevenueShareRecord)
            .filter(
                StreamerRevenueShareRecord.order_id == order_id,
                StreamerRevenueShareRecord.streamer_slug == streamer_slug,
            )
            .one_or_none()
        )

    @staticmethod
    def _ensure_record_matches(
        record: StreamerRevenueShareRecord,
        streamer: StreamerProfile,
        share: StreamerRevenueShare,
    ) -> StreamerRevenueShareRecord:
        if (
            record.streamer_profile_id != streamer.id
            or record.gross_amount != share.gross_amount
            or record.commission_bps != share.commission_bps
            or record.share_amount != share.share_amount
            or record.status != "pending"
        ):
            raise ValueError("revenue share record conflict")
        return record

    @staticmethod
    def _validate_required(value: str, message: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(message)
        return normalized

    @staticmethod
    def _validate_record_status(status: str) -> str:
        normalized_status = status.strip().lower()
        if normalized_status not in REVENUE_SHARE_TERMINAL_STATUSES:
            raise ValueError("status must be paid or void")
        return normalized_status

    @staticmethod
    def _validate_record_status_filter(status: str) -> str:
        normalized_status = status.strip().lower()
        if not normalized_status:
            raise ValueError("status is required")
        if normalized_status not in REVENUE_SHARE_RECORD_STATUSES:
            raise ValueError("status must be pending, paid, or void")
        return normalized_status

    @staticmethod
    def _validate_read_limit(limit: int) -> int:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        return limit

    @staticmethod
    def _normalize_optional_filter(value: str | None, message: str) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError(message)
        return normalized

    @classmethod
    def _normalize_created_range(
        cls,
        created_from: datetime | None,
        created_to: datetime | None,
    ) -> tuple[datetime | None, datetime | None]:
        normalized_created_from = cls._normalize_optional_datetime(created_from)
        normalized_created_to = cls._normalize_optional_datetime(created_to)
        if (
            normalized_created_from is not None
            and normalized_created_to is not None
            and normalized_created_from > normalized_created_to
        ):
            raise ValueError("invalid created_at range")
        return normalized_created_from, normalized_created_to

    @staticmethod
    def _normalize_optional_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    @staticmethod
    def _append_unique_product_id(
        product_ids: list[str],
        seen_product_ids: set[str],
        product_id: str,
    ) -> None:
        if product_id in seen_product_ids:
            return
        product_ids.append(product_id)
        seen_product_ids.add(product_id)
