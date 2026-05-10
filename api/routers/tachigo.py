from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import Settings, get_settings
from database import get_db
from security import verify_internal_secret
from services.identity_mapping_service import IdentityMappingService
from services.tachigo import TachigoUpstreamError, get_identity_points, get_user_points

router = APIRouter(prefix="/tachigo", tags=["tachigo"])


class TachigoPointsResponse(BaseModel):
    email: str
    spendable_balance: int
    cumulative_total: int


class TachigoIdentityPointsResponse(BaseModel):
    saleor_customer_id: str
    provider: str
    external_subject: str
    spendable_balance: int
    cumulative_total: int


@router.get(
    "/users/points",
    response_model=TachigoPointsResponse,
    dependencies=[Depends(verify_internal_secret)],
)
async def tachigo_user_points(
    email: str = Query(..., min_length=3),
    settings: Settings = Depends(get_settings),
):
    try:
        points = await get_user_points(email, settings)
    except TachigoUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return TachigoPointsResponse(
        email=points.email,
        spendable_balance=points.spendable_balance,
        cumulative_total=points.cumulative_total,
    )


@router.get(
    "/identity/points",
    response_model=TachigoIdentityPointsResponse,
    dependencies=[Depends(verify_internal_secret)],
)
async def tachigo_identity_points_by_query(
    provider: str = Query(..., min_length=1),
    external_subject: str = Query(..., min_length=1),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    return await _tachigo_identity_points_response(
        provider=provider,
        external_subject=external_subject,
        settings=settings,
        db=db,
    )


@router.get(
    "/identity/{provider}/{external_subject}/points",
    response_model=TachigoIdentityPointsResponse,
    dependencies=[Depends(verify_internal_secret)],
)
async def tachigo_identity_points(
    provider: str = Path(..., min_length=1),
    external_subject: str = Path(..., min_length=1),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    return await _tachigo_identity_points_response(
        provider=provider,
        external_subject=external_subject,
        settings=settings,
        db=db,
    )


async def _tachigo_identity_points_response(
    *,
    provider: str,
    external_subject: str,
    settings: Settings,
    db: Session,
) -> TachigoIdentityPointsResponse:
    normalized_provider = provider.strip().lower()
    if not normalized_provider:
        raise HTTPException(status_code=422, detail="provider is required")
    normalized_external_subject = external_subject.strip()
    if not normalized_external_subject:
        raise HTTPException(status_code=422, detail="external_subject is required")

    saleor_customer_id = IdentityMappingService(db).resolve_customer_id(
        normalized_provider,
        normalized_external_subject,
    )
    if saleor_customer_id is None:
        raise HTTPException(status_code=404, detail="identity mapping not found")

    try:
        points = await get_identity_points(normalized_provider, normalized_external_subject, settings)
    except TachigoUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return TachigoIdentityPointsResponse(
        saleor_customer_id=saleor_customer_id,
        provider=points.provider,
        external_subject=points.external_subject,
        spendable_balance=points.spendable_balance,
        cumulative_total=points.cumulative_total,
    )
