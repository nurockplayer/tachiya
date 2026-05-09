from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from database import get_db
from security import verify_internal_secret
from services.streamer_product_assignment_service import StreamerProductAssignmentService
from services.streamer_service import StreamerService

router = APIRouter(prefix="/streamers", tags=["streamers"])

NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class StreamerProfileCreateRequest(BaseModel):
    slug: NonBlankStr
    display_name: NonBlankStr
    saleor_collection_id: str | None = None
    commission_bps: int = Field(default=1000, ge=0, le=10000)
    active: bool = True


class StreamerProfileResponse(BaseModel):
    id: str
    slug: str
    display_name: str
    saleor_collection_id: str | None = None
    commission_bps: int
    active: bool
    created_at: datetime
    updated_at: datetime


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
    "/product-assignments/{saleor_product_id}",
    response_model=StreamerProductAssignmentResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def get_streamer_product_assignment(
    saleor_product_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
):
    assignment = StreamerProductAssignmentService(db).get_by_product_id(saleor_product_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="streamer product assignment not found")

    return _streamer_product_assignment_response(assignment)


@router.get(
    "/{slug}",
    response_model=StreamerProfileResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def get_streamer_profile(
    slug: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
):
    profile = StreamerService(db).get_by_slug(slug)
    if profile is None:
        raise HTTPException(status_code=404, detail="streamer profile not found")

    return _streamer_profile_response(profile)


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


def _streamer_product_assignment_response(assignment) -> StreamerProductAssignmentResponse:
    return StreamerProductAssignmentResponse(
        id=assignment.id,
        saleor_product_id=assignment.saleor_product_id,
        streamer_profile_id=assignment.streamer_profile_id,
        streamer_slug=assignment.streamer_slug,
        source=assignment.source,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
    )
