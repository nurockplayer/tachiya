from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field, StrictInt, StringConstraints
from sqlalchemy.orm import Session

from database import get_db
from security import (
    VerifiedWebhookRequest,
    verify_internal_secret,
    verify_webhook_signature,
)
from services.revenue_share_service import RevenueShareLine, RevenueShareService
from services.streamer_product_assignment_service import (
    StreamerProductAssignmentService,
)
from services.streamer_service import StreamerService
from services.webhook_event_service import WebhookEventReplayError, WebhookEventService

router = APIRouter(prefix="/streamers", tags=["streamers"])

NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class StreamerProfileCreateRequest(BaseModel):
    slug: NonBlankStr
    display_name: NonBlankStr
    saleor_collection_id: str | None = None
    commission_bps: StrictInt = Field(default=1000, ge=0, le=10000)
    active: bool = True


class StreamerProfileUpdateRequest(BaseModel):
    display_name: NonBlankStr | None = None
    saleor_collection_id: str | None = None
    commission_bps: StrictInt | None = Field(default=None, ge=0, le=10000)
    active: bool | None = None


class StreamerProfileResponse(BaseModel):
    id: str
    slug: str
    display_name: str
    saleor_collection_id: str | None = None
    commission_bps: int
    active: bool
    created_at: datetime
    updated_at: datetime


class StreamerProfileListResponse(BaseModel):
    profiles: list[StreamerProfileResponse]


class StreamerProductAssignmentRequest(BaseModel):
    saleor_product_id: NonBlankStr
    streamer_slug: NonBlankStr
    source: NonBlankStr = "manual"


class StreamerProductAssignmentResponse(BaseModel):
    id: str
    saleor_product_id: str
    streamer_profile_id: str
    streamer_slug: str
    source: str
    created_at: datetime
    updated_at: datetime


class StreamerProductAssignmentListResponse(BaseModel):
    assignments: list[StreamerProductAssignmentResponse]


class StreamerCatalogProfileResponse(BaseModel):
    slug: str
    display_name: str
    saleor_collection_id: str | None = None


class StreamerCatalogResponse(BaseModel):
    streamer: StreamerCatalogProfileResponse
    saleor_product_ids: list[str]


class StreamerListResponse(BaseModel):
    streamers: list[StreamerCatalogProfileResponse]


class RevenueSharePreviewLineRequest(BaseModel):
    saleor_product_id: NonBlankStr
    gross_amount: StrictInt = Field(gt=0)


class RevenueSharePreviewRequest(BaseModel):
    order_id: NonBlankStr
    lines: list[RevenueSharePreviewLineRequest] = Field(min_length=1)


class StreamerRevenueShareResponse(BaseModel):
    streamer_slug: str
    gross_amount: int
    commission_bps: int
    share_amount: int


class RevenueSharePreviewResponse(BaseModel):
    order_id: str
    shares: list[StreamerRevenueShareResponse]
    unassigned_product_ids: list[str]


class StreamerRevenueShareRecordResponse(BaseModel):
    id: str
    streamer_slug: str
    streamer_profile_id: str
    gross_amount: int
    commission_bps: int
    share_amount: int
    status: str
    created_at: datetime
    updated_at: datetime


class StreamerRevenueShareRecordListItemResponse(StreamerRevenueShareRecordResponse):
    order_id: str


class RevenueShareRecordResponse(BaseModel):
    order_id: str
    records: list[StreamerRevenueShareRecordResponse]
    unassigned_product_ids: list[str]


class RevenueShareRecordListResponse(BaseModel):
    records: list[StreamerRevenueShareRecordListItemResponse]


class RevenueShareRecordSummaryItemResponse(BaseModel):
    status: str
    record_count: int
    gross_amount: int
    share_amount: int


class RevenueShareRecordSummaryResponse(BaseModel):
    summaries: list[RevenueShareRecordSummaryItemResponse]


class RevenueShareRecordStatusRequest(BaseModel):
    status: NonBlankStr


class RevenueShareRecordStatusResponse(BaseModel):
    record: StreamerRevenueShareRecordListItemResponse


@router.post(
    "",
    response_model=StreamerProfileResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def create_streamer_profile(
    req: StreamerProfileCreateRequest,
    db: Session = Depends(get_db),
):
    try:
        profile = StreamerService(db).create_profile(
            slug=req.slug,
            display_name=req.display_name,
            saleor_collection_id=req.saleor_collection_id,
            commission_bps=req.commission_bps,
            active=req.active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return _streamer_profile_response(profile)


@router.get(
    "",
    response_model=StreamerListResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def list_streamer_profiles(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    profiles = StreamerService(db).list_active_profiles(limit=limit)
    return StreamerListResponse(
        streamers=[
            StreamerCatalogProfileResponse(
                slug=profile.slug,
                display_name=profile.display_name,
                saleor_collection_id=profile.saleor_collection_id,
            )
            for profile in profiles
        ],
    )


@router.get(
    "/profiles",
    response_model=StreamerProfileListResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def list_streamer_profiles_for_admin(
    active: bool | None = Query(default=None),
    slug: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    try:
        profiles = StreamerService(db).list_profiles(
            active=active,
            slug=slug,
            created_from=created_from,
            created_to=created_to,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return StreamerProfileListResponse(
        profiles=[_streamer_profile_response(profile) for profile in profiles],
    )


@router.post(
    "/product-assignments",
    response_model=StreamerProductAssignmentResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def assign_streamer_product(
    req: StreamerProductAssignmentRequest,
    db: Session = Depends(get_db),
):
    try:
        assignment = StreamerProductAssignmentService(db).assign_product(
            saleor_product_id=req.saleor_product_id,
            streamer_slug=req.streamer_slug,
            source=req.source,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail == "streamer profile not found" else 409
        raise HTTPException(status_code=status_code, detail=detail) from exc

    return _streamer_product_assignment_response(assignment)


@router.get(
    "/product-assignments",
    response_model=StreamerProductAssignmentListResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def list_streamer_product_assignments(
    streamer_slug: str | None = Query(default=None),
    source: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    try:
        assignments = StreamerProductAssignmentService(db).list_assignments(
            streamer_slug=streamer_slug,
            source=source,
            created_from=created_from,
            created_to=created_to,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return StreamerProductAssignmentListResponse(
        assignments=[
            _streamer_product_assignment_response(assignment)
            for assignment in assignments
        ],
    )


@router.get(
    "/revenue-shares/records",
    response_model=RevenueShareRecordListResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def list_streamer_revenue_share_records(
    status: str | None = Query(default=None),
    streamer_slug: str | None = Query(default=None),
    order_id: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    try:
        records = RevenueShareService(db).list_records(
            status=status,
            streamer_slug=streamer_slug,
            order_id=order_id,
            created_from=created_from,
            created_to=created_to,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return RevenueShareRecordListResponse(
        records=[
            _revenue_share_record_list_item_response(record) for record in records
        ],
    )


@router.get(
    "/revenue-shares/summary",
    response_model=RevenueShareRecordSummaryResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def summarize_streamer_revenue_share_records(
    status: str | None = Query(default=None),
    streamer_slug: str | None = Query(default=None),
    order_id: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        summaries = RevenueShareService(db).summarize_records(
            status=status,
            streamer_slug=streamer_slug,
            order_id=order_id,
            created_from=created_from,
            created_to=created_to,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return RevenueShareRecordSummaryResponse(
        summaries=[
            RevenueShareRecordSummaryItemResponse(
                status=summary.status,
                record_count=summary.record_count,
                gross_amount=summary.gross_amount,
                share_amount=summary.share_amount,
            )
            for summary in summaries
        ],
    )


@router.post(
    "/revenue-shares/records/{record_id}/status",
    response_model=RevenueShareRecordStatusResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def update_streamer_revenue_share_record_status(
    req: RevenueShareRecordStatusRequest,
    record_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
):
    try:
        record = RevenueShareService(db).update_record_status(
            record_id=record_id,
            status=req.status,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "revenue share record not found":
            raise HTTPException(status_code=404, detail=detail) from exc
        if detail == "revenue share status conflict":
            raise HTTPException(status_code=409, detail=detail) from exc
        raise HTTPException(status_code=422, detail=detail) from exc

    return RevenueShareRecordStatusResponse(
        record=_revenue_share_record_list_item_response(record),
    )


@router.post(
    "/revenue-shares/preview",
    response_model=RevenueSharePreviewResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def preview_streamer_revenue_shares(
    req: RevenueSharePreviewRequest,
    db: Session = Depends(get_db),
):
    try:
        preview = RevenueShareService(db).preview_order_share(
            order_id=req.order_id,
            lines=[
                RevenueShareLine(
                    saleor_product_id=line.saleor_product_id,
                    gross_amount=line.gross_amount,
                )
                for line in req.lines
            ],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RevenueSharePreviewResponse(
        order_id=preview.order_id,
        shares=[
            StreamerRevenueShareResponse(
                streamer_slug=share.streamer_slug,
                gross_amount=share.gross_amount,
                commission_bps=share.commission_bps,
                share_amount=share.share_amount,
            )
            for share in preview.shares
        ],
        unassigned_product_ids=preview.unassigned_product_ids,
    )


@router.post(
    "/revenue-shares/record",
    response_model=RevenueShareRecordResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def record_streamer_revenue_shares(
    req: RevenueSharePreviewRequest,
    db: Session = Depends(get_db),
):
    try:
        result = RevenueShareService(db).record_order_share(
            order_id=req.order_id,
            lines=[
                RevenueShareLine(
                    saleor_product_id=line.saleor_product_id,
                    gross_amount=line.gross_amount,
                )
                for line in req.lines
            ],
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return RevenueShareRecordResponse(
        order_id=result.order_id,
        records=[
            StreamerRevenueShareRecordResponse(
                id=record.id,
                streamer_slug=record.streamer_slug,
                streamer_profile_id=record.streamer_profile_id,
                gross_amount=record.gross_amount,
                commission_bps=record.commission_bps,
                share_amount=record.share_amount,
                status=record.status,
                created_at=record.created_at,
                updated_at=record.updated_at,
            )
            for record in result.records
        ],
        unassigned_product_ids=result.unassigned_product_ids,
    )


@router.post(
    "/webhooks/order-completed",
    response_model=RevenueShareRecordResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def record_streamer_revenue_shares_from_order_webhook(
    req: RevenueSharePreviewRequest,
    webhook: VerifiedWebhookRequest | None = Depends(verify_webhook_signature),
    db: Session = Depends(get_db),
):
    _reject_replayed_webhook_event(db, webhook)
    try:
        result = RevenueShareService(db).record_order_share(
            order_id=req.order_id,
            lines=[
                RevenueShareLine(
                    saleor_product_id=line.saleor_product_id,
                    gross_amount=line.gross_amount,
                )
                for line in req.lines
            ],
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    _record_webhook_event(db, webhook, event_type="revenue_share.order_completed")
    return _revenue_share_record_response(result)


@router.get(
    "/product-assignments/{saleor_product_id}",
    response_model=StreamerProductAssignmentResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def get_streamer_product_assignment(
    saleor_product_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
):
    normalized_product_id = _normalize_path_param(
        saleor_product_id,
        "saleor_product_id is required",
    )
    assignment = StreamerProductAssignmentService(db).get_by_product_id(
        normalized_product_id
    )
    if assignment is None:
        raise HTTPException(
            status_code=404, detail="streamer product assignment not found"
        )

    return _streamer_product_assignment_response(assignment)


@router.delete(
    "/product-assignments/{saleor_product_id}",
    response_model=StreamerProductAssignmentResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def delete_streamer_product_assignment(
    saleor_product_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
):
    normalized_product_id = _normalize_path_param(
        saleor_product_id,
        "saleor_product_id is required",
    )
    assignment = StreamerProductAssignmentService(db).remove_product(
        normalized_product_id
    )
    if assignment is None:
        raise HTTPException(
            status_code=404, detail="streamer product assignment not found"
        )

    return _streamer_product_assignment_response(assignment)


@router.get(
    "/{slug}/catalog",
    response_model=StreamerCatalogResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def get_streamer_catalog(
    slug: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
):
    normalized_slug = _normalize_path_param(slug, "slug is required")
    profile = StreamerService(db).get_by_slug(normalized_slug)
    if profile is None or not profile.active:
        raise HTTPException(status_code=404, detail="streamer catalog not found")

    saleor_product_ids = StreamerProductAssignmentService(
        db
    ).list_product_ids_for_streamer(
        profile.slug,
    )
    return StreamerCatalogResponse(
        streamer=StreamerCatalogProfileResponse(
            slug=profile.slug,
            display_name=profile.display_name,
            saleor_collection_id=profile.saleor_collection_id,
        ),
        saleor_product_ids=saleor_product_ids,
    )


@router.patch(
    "/{slug}",
    response_model=StreamerProfileResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def update_streamer_profile(
    req: StreamerProfileUpdateRequest,
    slug: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
):
    if not req.model_fields_set:
        raise HTTPException(status_code=422, detail="at least one field is required")

    update_kwargs = {
        field_name: getattr(req, field_name) for field_name in req.model_fields_set
    }
    normalized_slug = _normalize_path_param(slug, "slug is required")
    try:
        profile = StreamerService(db).update_profile(normalized_slug, **update_kwargs)
    except ValueError as exc:
        detail = str(exc)
        if detail == "streamer profile not found":
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=409, detail=detail) from exc

    return _streamer_profile_response(profile)


@router.get(
    "/{slug}",
    response_model=StreamerProfileResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def get_streamer_profile(
    slug: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
):
    normalized_slug = _normalize_path_param(slug, "slug is required")
    profile = StreamerService(db).get_by_slug(normalized_slug)
    if profile is None:
        raise HTTPException(status_code=404, detail="streamer profile not found")

    return _streamer_profile_response(profile)


def _normalize_path_param(value: str, message: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise HTTPException(status_code=422, detail=message)
    return normalized


def _streamer_profile_response(profile) -> StreamerProfileResponse:
    return StreamerProfileResponse(
        id=profile.id,
        slug=profile.slug,
        display_name=profile.display_name,
        saleor_collection_id=profile.saleor_collection_id,
        commission_bps=profile.commission_bps,
        active=profile.active,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _streamer_product_assignment_response(
    assignment,
) -> StreamerProductAssignmentResponse:
    return StreamerProductAssignmentResponse(
        id=assignment.id,
        saleor_product_id=assignment.saleor_product_id,
        streamer_profile_id=assignment.streamer_profile_id,
        streamer_slug=assignment.streamer_slug,
        source=assignment.source,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
    )


def _revenue_share_record_response(result) -> RevenueShareRecordResponse:
    return RevenueShareRecordResponse(
        order_id=result.order_id,
        records=[
            StreamerRevenueShareRecordResponse(
                id=record.id,
                streamer_slug=record.streamer_slug,
                streamer_profile_id=record.streamer_profile_id,
                gross_amount=record.gross_amount,
                commission_bps=record.commission_bps,
                share_amount=record.share_amount,
                status=record.status,
                created_at=record.created_at,
                updated_at=record.updated_at,
            )
            for record in result.records
        ],
        unassigned_product_ids=result.unassigned_product_ids,
    )


def _revenue_share_record_list_item_response(
    record,
) -> StreamerRevenueShareRecordListItemResponse:
    return StreamerRevenueShareRecordListItemResponse(
        id=record.id,
        order_id=record.order_id,
        streamer_slug=record.streamer_slug,
        streamer_profile_id=record.streamer_profile_id,
        gross_amount=record.gross_amount,
        commission_bps=record.commission_bps,
        share_amount=record.share_amount,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _reject_replayed_webhook_event(
    db: Session,
    webhook: VerifiedWebhookRequest | None,
) -> None:
    try:
        WebhookEventService(db).reject_replayed_event(webhook)
    except WebhookEventReplayError as exc:
        raise HTTPException(
            status_code=409, detail="webhook event already processed"
        ) from exc


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
