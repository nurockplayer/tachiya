from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.streamer import StreamerProfile

_UNSET = object()


class StreamerService:
    def __init__(self, db: Session):
        self.db = db

    def create_profile(
        self,
        *,
        slug: str,
        display_name: str,
        saleor_collection_id: str | None = None,
        commission_bps: int = 1000,
        active: bool = True,
    ) -> StreamerProfile:
        normalized_slug = self._normalize_slug(slug)
        normalized_display_name = self._validate_required(
            display_name,
            "display_name is required",
        )
        normalized_collection_id = self._normalize_optional(saleor_collection_id)
        self._validate_commission_bps(commission_bps)

        profile = StreamerProfile(
            slug=normalized_slug,
            display_name=normalized_display_name,
            saleor_collection_id=normalized_collection_id,
            commission_bps=commission_bps,
            active=active,
        )
        self.db.add(profile)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("streamer profile already exists") from exc
        self.db.refresh(profile)
        return profile

    def update_profile(
        self,
        slug: str,
        *,
        display_name=_UNSET,
        saleor_collection_id=_UNSET,
        commission_bps=_UNSET,
        active=_UNSET,
    ) -> StreamerProfile:
        profile = self.get_by_slug(slug)
        if profile is None:
            raise ValueError("streamer profile not found")

        if display_name is not _UNSET and display_name is not None:
            profile.display_name = self._validate_required(
                display_name,
                "display_name is required",
            )
        if saleor_collection_id is not _UNSET:
            profile.saleor_collection_id = self._normalize_optional(saleor_collection_id)
        if commission_bps is not _UNSET and commission_bps is not None:
            self._validate_commission_bps(commission_bps)
            profile.commission_bps = commission_bps
        if active is not _UNSET and active is not None:
            profile.active = active

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("streamer profile already exists") from exc
        self.db.refresh(profile)
        return profile

    def get_by_slug(self, slug: str) -> StreamerProfile | None:
        normalized_slug = self._normalize_slug(slug)
        return (
            self.db.query(StreamerProfile)
            .filter(StreamerProfile.slug == normalized_slug)
            .one_or_none()
        )

    def list_active_profiles(self, *, limit: int = 20) -> list[StreamerProfile]:
        return (
            self.db.query(StreamerProfile)
            .filter(StreamerProfile.active.is_(True))
            .order_by(StreamerProfile.display_name.asc(), StreamerProfile.slug.asc())
            .limit(limit)
            .all()
        )

    def list_profiles(
        self,
        *,
        active: bool | None = None,
        slug: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int = 20,
    ) -> list[StreamerProfile]:
        normalized_slug = self._normalize_optional_filter(slug, "slug is required")
        normalized_created_from = self._normalize_optional_datetime(created_from)
        normalized_created_to = self._normalize_optional_datetime(created_to)
        if (
            normalized_created_from is not None
            and normalized_created_to is not None
            and normalized_created_from > normalized_created_to
        ):
            raise ValueError("invalid created_at range")

        query = self.db.query(StreamerProfile)
        if active is not None:
            query = query.filter(StreamerProfile.active.is_(active))
        if normalized_slug is not None:
            query = query.filter(StreamerProfile.slug == normalized_slug.lower())
        if normalized_created_from is not None:
            query = query.filter(StreamerProfile.created_at >= normalized_created_from)
        if normalized_created_to is not None:
            query = query.filter(StreamerProfile.created_at <= normalized_created_to)

        return (
            query.order_by(StreamerProfile.display_name.asc(), StreamerProfile.slug.asc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def _normalize_slug(slug: str) -> str:
        return StreamerService._validate_required(slug, "slug is required").lower()

    @staticmethod
    def _normalize_optional(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

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
    def _validate_required(value: str, message: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(message)
        return normalized

    @staticmethod
    def _validate_commission_bps(commission_bps: int) -> None:
        if commission_bps < 0 or commission_bps > 10000:
            raise ValueError("commission_bps must be between 0 and 10000")
