from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from config import Settings, get_settings
from security import verify_internal_secret
from services.tachigo import TachigoUpstreamError, get_user_points

router = APIRouter(prefix="/tachigo", tags=["tachigo"])


class TachigoPointsResponse(BaseModel):
    email: str
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
