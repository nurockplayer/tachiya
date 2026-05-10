from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.streamer import StreamerProductAssignment
from services.streamer_service import StreamerService


class StreamerProductAssignmentService:
    def __init__(self, db: Session):
        self.db = db
        self.streamers = StreamerService(db)

    def assign_product(
        self,
        *,
        saleor_product_id: str,
        streamer_slug: str,
        source: str = "manual",
    ) -> StreamerProductAssignment:
        normalized_product_id = self._validate_required(
            saleor_product_id,
            "saleor_product_id is required",
        )
        normalized_source = self._validate_required(source, "source is required")
        streamer = self.streamers.get_by_slug(streamer_slug)
        if streamer is None:
            raise ValueError("streamer profile not found")

        existing_assignment = self.get_by_product_id(normalized_product_id)
        if existing_assignment is not None:
            existing_assignment.streamer_profile_id = streamer.id
            existing_assignment.streamer_slug = streamer.slug
            existing_assignment.source = normalized_source
            self.db.commit()
            self.db.refresh(existing_assignment)
            return existing_assignment

        assignment = StreamerProductAssignment(
            saleor_product_id=normalized_product_id,
            streamer_profile_id=streamer.id,
            streamer_slug=streamer.slug,
            source=normalized_source,
        )
        self.db.add(assignment)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("streamer product assignment already exists") from exc
        self.db.refresh(assignment)
        return assignment

    def get_by_product_id(self, saleor_product_id: str) -> StreamerProductAssignment | None:
        normalized_product_id = self._validate_required(
            saleor_product_id,
            "saleor_product_id is required",
        )
        return (
            self.db.query(StreamerProductAssignment)
            .filter(StreamerProductAssignment.saleor_product_id == normalized_product_id)
            .one_or_none()
        )

    def list_product_ids_for_streamer(self, streamer_slug: str) -> list[str]:
        normalized_slug = StreamerService._normalize_slug(streamer_slug)
        assignments = (
            self.db.query(StreamerProductAssignment)
            .filter(StreamerProductAssignment.streamer_slug == normalized_slug)
            .order_by(
                StreamerProductAssignment.created_at.asc(),
                StreamerProductAssignment.id.asc(),
            )
            .all()
        )
        return [assignment.saleor_product_id for assignment in assignments]

    def list_assignments(
        self,
        *,
        streamer_slug: str | None = None,
        source: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int = 20,
    ) -> list[StreamerProductAssignment]:
        normalized_limit = self._validate_read_limit(limit)
        normalized_streamer_slug = self._normalize_optional_filter(
            streamer_slug,
            "streamer_slug is required",
        )
        normalized_source = self._normalize_optional_filter(source, "source is required")
        normalized_created_from = self._normalize_optional_datetime(created_from)
        normalized_created_to = self._normalize_optional_datetime(created_to)
        if (
            normalized_created_from is not None
            and normalized_created_to is not None
            and normalized_created_from > normalized_created_to
        ):
            raise ValueError("invalid created_at range")

        query = self.db.query(StreamerProductAssignment)
        if normalized_streamer_slug is not None:
            query = query.filter(
                StreamerProductAssignment.streamer_slug == normalized_streamer_slug.lower(),
            )
        if normalized_source is not None:
            query = query.filter(StreamerProductAssignment.source == normalized_source)
        if normalized_created_from is not None:
            query = query.filter(StreamerProductAssignment.created_at >= normalized_created_from)
        if normalized_created_to is not None:
            query = query.filter(StreamerProductAssignment.created_at <= normalized_created_to)

        return (
            query.order_by(
                StreamerProductAssignment.created_at.desc(),
                StreamerProductAssignment.id.asc(),
            )
            .limit(normalized_limit)
            .all()
        )

    def remove_product(self, saleor_product_id: str) -> StreamerProductAssignment | None:
        assignment = self.get_by_product_id(saleor_product_id)
        if assignment is None:
            return None

        self.db.delete(assignment)
        self.db.commit()
        return assignment

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

    @staticmethod
    def _normalize_optional_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    @staticmethod
    def _validate_read_limit(limit: int) -> int:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        return limit
