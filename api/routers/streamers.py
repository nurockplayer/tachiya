from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from database import get_db
from security import verify_internal_secret
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
